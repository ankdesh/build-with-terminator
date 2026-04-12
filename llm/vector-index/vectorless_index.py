import os
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

# Try to import Docling, handle the case where it might be still installing
try:
    from docling.document_converter import DocumentConverter
    from docling.chunking import HierarchicalChunker
except ImportError as e:
    DocumentConverter = None
    HierarchicalChunker = None
    print(f"Docling imports failed: {e}. Please ensure docling is installed.")

class NodeSummary(BaseModel):
    summary: str = Field(description="A concise but highly informative summary of what this section contains.")

class ReasoningResult(BaseModel):
    thinking: str = Field(description="Step by step reasoning about which section contains the answer to the query.")
    selected_node_id: str = Field(description="The exact ID of the node that is most likely to contain the answer.")

class IndexNode:
    def __init__(self, node_id: str, headings: List[str], text: str, summary: str = ""):
        self.node_id = node_id
        self.headings = headings
        self.text = text
        self.summary = summary

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "headings": self.headings,
            "summary": self.summary
        }

class LocalPageIndex:
    """
    A custom vectorless reasoning-based page index using Docling and OpenAI.
    """
    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        if not DocumentConverter:
            raise RuntimeError("Docling is required. Please install with `pip install docling`.")
        self.client = OpenAI(api_key=openai_api_key)
        self.model = model
        self.nodes: Dict[str, IndexNode] = {}
        self.tree_structure: List[Dict[str, Any]] = []
    
    def parse_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parses a PDF into a hierarchical chunks using Docling and summarizes each node.
        """
        print(f"Parsing document with Docling: {file_path}")
        converter = DocumentConverter()
        result = converter.convert(file_path)
        doc = result.document
        
        chunker = HierarchicalChunker(merge_list_items=True)
        chunks = list(chunker.chunk(doc))
        
        print(f"Generated {len(chunks)} chunks. Summarizing sections with LLM...")
        
        self.nodes = {}
        self.tree_structure = []
        
        for i, chunk in enumerate(chunks):
            node_id = f"node_{i}"
            text = chunk.text
            headings = chunk.meta.headings if hasattr(chunk.meta, 'headings') else []
            
            # Using LLM to summarize the content
            prompt = (
                f"You are extracting the core purpose of a document section.\n"
                f"Headings: {', '.join(headings) if headings else 'Root/None'}\n"
                f"Text:\n{text[:2000]}...\n\n"
                f"Provide a short, concise summary of what this section covers, in 2-3 sentences."
            )
            
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                response_format=NodeSummary
            )
            
            summary = completion.choices[0].message.parsed.summary
            
            node = IndexNode(node_id=node_id, headings=headings, text=text, summary=summary)
            self.nodes[node_id] = node
            self.tree_structure.append(node.to_dict())
            
            print(f"Processed {node_id}: {headings}")
            
        return self.tree_structure

    def traverse_index(self):
        """
        Prints the summary tree of the indexed document.
        """
        if not self.tree_structure:
            print("Index is empty. Parse a document first.")
            return
            
        print("\n=== Document Index Tree ===")
        for node_dict in self.tree_structure:
            headings_str = " > ".join(node_dict['headings']) if node_dict['headings'] else "Root Level"
            print(f"[{node_dict['node_id']}] {headings_str}")
            print(f"Summary: {node_dict['summary']}\n")
    
    def query_index(self, query: str) -> Dict[str, Any]:
        """
        Submits a query to the LLM index without vector search. 
        It evaluates the tree and selects the best node.
        """
        if not self.tree_structure:
            raise ValueError("Index is empty. Parse a document first.")
            
        print(f"Reasoning over index tree for query: '{query}'")
        
        # Present the entire tree structure to the LLM
        tree_json = json.dumps(self.tree_structure, indent=2)
        
        prompt = (
            f"You are an intelligent document router.\n"
            f"Here is the hierarchical index of a document, where each node has an ID and a summary:\n"
            f"{tree_json}\n\n"
            f"User Query: {query}\n\n"
            f"Evaluate the summaries. Reason which node_id is most likely to contain the exact answer to the user's query.\n"
            f"Ensure you return a valid node_id from the list provided."
        )
        
        completion = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a logical document router."},
                {"role": "user", "content": prompt}
            ],
            response_format=ReasoningResult
        )
        
        reasoning_result = completion.choices[0].message.parsed
        selected_node_id = reasoning_result.selected_node_id
        
        if selected_node_id not in self.nodes:
            return {
                "error": f"LLM returned invalid node ID: {selected_node_id}",
                "thinking": reasoning_result.thinking
            }
        
        target_node = self.nodes[selected_node_id]
        
        return {
            "selected_node_id": selected_node_id,
            "headings": target_node.headings,
            "associated_text": target_node.text,
            "thinking": reasoning_result.thinking
        }
