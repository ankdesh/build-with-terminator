# **Automated Specification Decomposition for SystemC Virtual Platform Generation: A Docling-Based Parsing Architecture**

Electronic System-Level (ESL) design automation relies on transforming informal architectural specification documents into structured, executable virtual prototypes1. Hardware architecture documents—typically distributed as unstructured PDF files—contain rich hierarchical descriptions of system components, register transfer specifications, memory maps, and interconnect topologies1. To automatically synthesize these specifications into SystemC modeling structures (sc\_module), the underlying text, figures, and tabular data must be decomposed into bounded semantic sections while maintaining structural lineage1.  
Extracting structured content from Portable Document Format (PDF) files introduces significant technical challenges due to the programmatic detachment of spatial visual elements from logical document hierarchies1. A robust document ingestion pipeline must execute layout analysis, segment multi-column text flows, extract structural tables, isolate visual architectural diagrams, and generate modular Markdown representations containing precise local references to externalized assets1.

## **Comparative Evaluation of Open-Source Document Parsing Frameworks**

Selecting an open-source parsing engine for hardware specification processing requires evaluating visual layout models, hierarchical document tree extraction, structural table recovery, and license compatibility for corporate Electronic Design Automation (EDA) workflows3. Several high-performance open-source frameworks have emerged to handle complex document parsing tasks.

| Framework | Core Layout & Vision Engine | License | Section Hierarchy Extraction | Table & Image Externalization | Suitability for SystemC Toolchains |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Docling (IBM Research)** | Layout Transformer \+ TableFormer \+ VLM options5 | MIT5 | Native document structure tree (DoclingDocument)1 | Native API export for PIL images and structured data1 | **Optimal**: Directly maps hierarchical document nodes to SystemC ASTs1. |
| **Marker (Datalab)** | Surya VLM \+ Texify3 | GPL-3.0 / CC-BY-NC-SA-4.0 (Model weights)3 | Post-processed heading hierarchy tags3 | Image extraction and inline table formatting3 | **Moderate**: High accuracy, but licensing limits commercial EDA integrations3. |
| **MinerU (Magic-PDF)** | Layoutlmv3 \+ Custom OCR9 | AGPL-3.010 | Page and block level extraction10 | Extraction to localized subdirectories10 | **Moderate**: Heavy runtime footprint and restrictive licensing model10. |
| **PyMuPDF / PyMuPDF4LLM** | Heuristic layout rules & MuPDF C Engine11 | AGPL-3.0 / Commercial11 | Regex/Heuristic heading detection11 | Raw bitmap extraction and text-table conversion11 | **Low**: Lacks deep AI visual layout modeling for multi-column hardware specs1. |

Comparative analysis identifies IBM Docling as the superior framework for preparing architectural documents for SystemC platform generation1. Docling abstracts raw PDF primitives into a unified, expressive DoclingDocument object model5. This model preserves semantic reading order, detects complex nested tables using the specialized TableFormer neural architecture, isolates visual elements with spatial bounding coordinates, and exposes document elements via a traversable Abstract Syntax Tree (AST)4. Furthermore, Docling's permissive MIT license eliminates commercial restrictions within proprietary hardware design software toolchains3.

## **Pipeline Architecture for Specification Decomposition**

The process of converting an unstructured architectural specification into modular SystemC-ready components follows a deterministic, five-stage ingestion pipeline1. The system decouples raw visual primitives into explicit semantic categories—narrative prose, tabular data matrices, and visual block diagrams—ensuring that downstream code generators receive fully self-contained section files1.

| Pipeline Stage | Primary Operation | Inputs | Outputs / Artifacts |
| :---- | :---- | :---- | :---- |
| **1\. Pipeline Initialization** | Configure resolution scaling, table recovery flags, and image extraction parameters1. | PDF File Path, Runtime Configuration Flags7 | DocumentConverter Instance1 |
| **2\. Layout & Vision Analysis** | Perform object detection, reading order recovery, and table boundary detection5. | Binary PDF Stream14 | In-Memory DoclingDocument AST1 |
| **3\. AST Traversal & Asset Decoupling** | Walk the document tree, isolate PictureItem and TableItem nodes, and write files1. | DoclingDocument Object1 | PNG Figures, CSV Data Files1 |
| **4\. Sectional Markdown Generation** | Accumulate narrative text under detected $H\_1$ and $H\_2$ section headers1. | Text Nodes, Relative Asset Paths1 | Bounded Markdown (.md) Files1 |
| **5\. Manifest Generation** | Compile document tree metadata and section boundaries into machine-readable JSON1. | Section File List, Asset Metadata | parsing\_manifest.json \[cite: 1\] |

The ingestion process begins by initializing the DocumentConverter with custom PdfPipelineOptions7. The system sets an explicit scaling factor (images\_scale \= 2.0) to render graphical primitives at high resolution (144 DPI), ensuring that intricate hardware timing diagrams and bus topologies retain sharpness when saved externally7. The layout engine parses the document vector stream, applying object detection models to locate paragraphs, section headers, code snippets, figures, and tables1.  
Once the document structure is mapped into memory as a DoclingDocument object, an AST walker iterates sequentially through every structural block1. When the walker encounters a major section header (![][image1] or ![][image2]), it flushes the active text buffer into a dedicated Markdown file and opens a new section buffer1. When visual pictures or tables are encountered, the engine extracts the underlying bitmap or data frame, writes the content to an asset subfolder (./assets/figures/ or ./assets/tables/), and injects a relative POSIX link directly into the section's Markdown buffer1. Finally, a master JSON manifest is produced to map the complete document structure for downstream EDA synthesis scripts1.

## **Production Python Implementation**

The following complete Python module leverages Docling to segment an architectural PDF into isolated Markdown sections, extract graphical and tabular assets, and output an integration manifest.

Python  
import os  
import re  
import json  
from pathlib import Path  
from typing import List, Dict, Any, Optional

from docling.document\_converter import DocumentConverter, PdfFormatOption  
from docling.datamodel.pipeline\_options import PdfPipelineOptions  
from docling.datamodel.base\_models import InputFormat  
from docling\_core.types.doc import (  
    DoclingDocument,  
    SectionHeaderItem,  
    TextItem,  
    TableItem,  
    PictureItem,  
)

class ArchitectureDocParser:  
    """  
    Parses architectural PDF specifications into modular Markdown sections  
    with externalized figure and table assets for SystemC virtual platform synthesis.  
    """

    def \_\_init\_\_(self, output\_dir: str \= "./extracted\_spec"):  
        self.output\_dir \= Path(output\_dir)  
        self.sections\_dir \= self.output\_dir / "sections"  
        self.figures\_dir \= self.output\_dir / "assets" / "figures"  
        self.tables\_dir \= self.output\_dir / "assets" / "tables"  
          
        self.\_create\_directories()  
        self.converter \= self.\_init\_converter()

    def \_create\_directories(self) \-\> None:  
        """Creates required output directory hierarchy."""  
        self.sections\_dir.mkdir(parents=True, exist\_ok=True)  
        self.figures\_dir.mkdir(parents=True, exist\_ok=True)  
        self.tables\_dir.mkdir(parents=True, exist\_ok=True)

    def \_init\_converter(self) \-\> DocumentConverter:  
        """Configures Docling pipeline with image extraction and high resolution."""  
        pipeline\_options \= PdfPipelineOptions()  
        pipeline\_options.generate\_picture\_images \= True  
        pipeline\_options.images\_scale \= 2.0  \# High DPI export for crisp block diagrams  
        pipeline\_options.do\_table\_structure \= True  
          
        return DocumentConverter(  
            format\_options={  
                InputFormat.PDF: PdfFormatOption(pipeline\_options=pipeline\_options)  
            }  
        )

    def \_sanitize\_filename(self, name: str) \-\> str:  
        """Converts section headers into clean filesystem identifiers."""  
        clean\_name \= re.sub(r'\[^\\w\\s-\]', '', name).strip().lower()  
        return re.sub(r'\[-\\s\]+', '\_', clean\_name)

    def parse\_pdf(self, pdf\_path: str) \-\> List\[Path\]:  
        """  
        Executes full extraction pipeline on target PDF file.  
        Returns a list of generated section Markdown file paths.  
        """  
        pdf\_file \= Path(pdf\_path)  
        if not pdf\_file.exists():  
            raise FileNotFoundError(f"Architectural document not found: {pdf\_path}")

        print(f"Parsing architectural specification: {pdf\_file.name}...")  
        conversion\_result \= self.converter.convert(pdf\_file)  
        doc: DoclingDocument \= conversion\_result.document

        return self.\_process\_document\_tree(doc, pdf\_file.stem)

    def \_process\_document\_tree(self, doc: DoclingDocument, doc\_stem: str) \-\> List\[Path\]:  
        """Traverses Docling structural AST and extracts section-bounded markdown files."""  
        section\_files: List\[Path\] \= \[\]  
          
        current\_section\_title \= "00\_introduction\_and\_overview"  
        current\_section\_idx \= 0  
        current\_buffer: List\[str\] \= \[\]  
          
        figure\_counter \= 0  
        table\_counter \= 0

        def flush\_section\_buffer(title: str, index: int, content: List\[str\]) \-\> Optional\[Path\]:  
            if not content:  
                return None  
            filename \= f"section\_{index:02d}\_{self.\_sanitize\_filename(title)}.md"  
            filepath \= self.sections\_dir / filename  
              
            with open(filepath, "w", encoding="utf-8") as f:  
                f.write(f"\# Section: {title}\\n\\n")  
                f.write("\\n\\n".join(content))  
            print(f"Exported Section \-\> {filepath.name}")  
            return filepath

        for item, level in doc.iterate\_items():  
            if isinstance(item, SectionHeaderItem):  
                header\_level \= getattr(item, "level", 1)  
                header\_text \= item.text.strip()

                \# Boundary condition: major section headers trigger a buffer flush  
                if header\_level \<= 2 and current\_buffer:  
                    saved\_path \= flush\_section\_buffer(  
                        current\_section\_title, current\_section\_idx, current\_buffer  
                    )  
                    if saved\_path:  
                        section\_files.append(saved\_path)  
                      
                    current\_section\_idx \+= 1  
                    current\_section\_title \= header\_text  
                    current\_buffer \= \[\]

                prefix \= "\#" \* header\_level  
                current\_buffer.append(f"{prefix} {header\_text}")

            elif isinstance(item, TextItem):  
                if item.text.strip():  
                    current\_buffer.append(item.text.strip())

            elif isinstance(item, PictureItem):  
                figure\_counter \+= 1  
                fig\_filename \= f"{doc\_stem}\_fig\_{figure\_counter:03d}.png"  
                fig\_path \= self.figures\_dir / fig\_filename  
                  
                image\_obj \= item.get\_image(doc)  
                if image\_obj:  
                    image\_obj.save(fig\_path, format\="PNG")  
                      
                    rel\_fig\_path \= os.path.relpath(fig\_path, self.sections\_dir)  
                    caption\_text \= item.caption\_text(doc) if hasattr(item, "caption\_text") else ""  
                    alt\_text \= caption\_text if caption\_text else f"Architectural Diagram {figure\_counter}"  
                      
                    md\_image\_ref \= f"\!\[{alt\_text}\]({rel\_fig\_path})"  
                    if caption\_text:  
                        md\_image\_ref \+= f"\\n\*Figure {figure\_counter}: {caption\_text}\*"  
                      
                    current\_buffer.append(md\_image\_ref)

            elif isinstance(item, TableItem):  
                table\_counter \+= 1  
                tbl\_csv\_filename \= f"{doc\_stem}\_table\_{table\_counter:03d}.csv"  
                tbl\_csv\_path \= self.tables\_dir / tbl\_csv\_filename  
                  
                try:  
                    df \= item.export\_to\_dataframe()  
                    df.to\_csv(tbl\_csv\_path, index=False)  
                except Exception:  
                    pass

                table\_md \= item.export\_to\_markdown(doc=doc)  
                rel\_tbl\_path \= os.path.relpath(tbl\_csv\_path, self.sections\_dir)  
                  
                caption\_text \= item.caption\_text(doc) if hasattr(item, "caption\_text") else ""  
                tbl\_block \= f"\<\!-- External Data: \[{tbl\_csv\_filename}\]({rel\_tbl\_path}) \--\>\\n" \+ table\_md  
                if caption\_text:  
                    tbl\_block \+= f"\\n\*Table {table\_counter}: {caption\_text}\*"  
                  
                current\_buffer.append(tbl\_block)

        if current\_buffer:  
            saved\_path \= flush\_section\_buffer(  
                current\_section\_title, current\_section\_idx, current\_buffer  
            )  
            if saved\_path:  
                section\_files.append(saved\_path)

        self.\_generate\_manifest(doc\_stem, section\_files, figure\_counter, table\_counter)  
        return section\_files

    def \_generate\_manifest(  
        self, doc\_stem: str, sections: List\[Path\], fig\_count: int, tbl\_count: int  
    ) \-\> None:  
        """Generates JSON manifest mapping output structure for EDA toolchains."""  
        manifest \= {  
            "specification\_name": doc\_stem,  
            "total\_sections": len(sections),  
            "total\_figures": fig\_count,  
            "total\_tables": tbl\_count,  
            "sections": \[p.name for p in sections\],  
            "asset\_paths": {  
                "figures": str(self.figures\_dir.resolve()),  
                "tables": str(self.tables\_dir.resolve()),  
            },  
        }  
        manifest\_path \= self.output\_dir / "parsing\_manifest.json"  
        with open(manifest\_path, "w", encoding="utf-8") as f:  
            json.dump(manifest, f, indent=2)  
        print(f"Extraction Manifest saved to \-\> {manifest\_path}")

if \_\_name\_\_ \== "\_\_main\_\_":  
    import sys  
      
    target\_pdf \= sys.argv\[1\] if len(sys.argv) \> 1 else "soc\_architecture\_spec.pdf"  
      
    if os.path.exists(target\_pdf):  
        parser \= ArchitectureDocParser(output\_dir="./parsed\_arch\_spec")  
        generated\_sections \= parser.parse\_pdf(target\_pdf)  
        print(f"\\nProcessing complete. Generated {len(generated\_sections)} modular sections.")  
    else:  
        print(f"Usage: python {sys.argv\[0\]} \<path\_to\_architecture\_pdf\>")

## **Deep Architectural Analysis of Ingestion Subsystems**

Understanding the internal mechanics of Docling's engine clarifies how unstructured PDF vector streams are transformed into deterministic section outputs suitable for code generation1.

### **Optical Layout Recognition and Reading Order Recovery**

Standard PDF extractors retrieve text characters strictly based on their physical offset within the file stream1. In complex hardware specifications featuring multi-column memory maps, side-by-side register descriptions, and floating state-machine diagrams, this approach leads to interleaved, corrupted text strings1.  
Docling prevents text corruption by passing rendered page bitmaps through a ResNet/Transformer layout detection model5. The model identifies structural bounding boxes across six core classes: SectionHeader, Paragraph, Table, Picture, Caption, and Code2. A graph-based reading-order algorithm then connects adjacent bounding boxes, resolving multi-column flows and parent-child header hierarchies2.

### **Neural Table Extraction via TableFormer**

Hardware specifications rely heavily on complex tables to define register bit fields, memory maps, and pin assignments1. These tables frequently present challenging formatting, such as multi-row headers, merged cells, or missing grid borders1.  
Docling addresses this complexity through its integrated TableFormer neural model6. TableFormer predicts table structures independently of physical grid lines by processing visual bitmap regions alongside extracted text cell coordinates6. The network predicts logical structure tags (\<thead\>, \<tbody\>, colspan, rowspan) while mapping coordinates to individual cells6. This ensures multi-bit register maps remain properly aligned when exported to CSV or Markdown formats1.

### **Asset Decoupling and Relative Link Maintenance**

Including raw base64 image strings directly inside section Markdown files bloats file size and disrupts Large Language Model (LLM) context windows during downstream code synthesis7. The implementation uses Docling's get\_image() API to extract binary images directly from the PDF canvas1. Configuring images\_scale \= 2.0 renders vector graphics at double the standard DPI, preserving readability for detailed circuit diagrams7.  
When the parser encounters a PictureItem or TableItem, it saves the isolated asset to the respective subfolder (./assets/figures/ or ./assets/tables/)1. The script calculates the relative POSIX path between the section Markdown file and the asset location7. It then substitutes the raw image or table block with a clean relative reference:  
![][image3]  
This decoupled approach keeps text files lightweight for textual LLM processing while maintaining access to visual and tabular assets for vision-capable or spreadsheet models9.

## **Downstream Mapping to SystemC Virtual Platforms**

The modular Markdown sections produced by the pipeline directly inform the synthesis of SystemC simulation components2. Each extracted section file maps to a specific element within an Electronic System-Level (ESL) virtual platform architecture2.

C++  
// Downstream Synthesized Architecture Example  
// Section 03 (DMA Controller) \-\> sc\_module Representation

\#**include** \<systemc.h\>  
\#**include** \<tlm.h\>  
\#**include** "tlm\_utils/simple\_target\_socket.h"

SC\_MODULE(dma\_controller) {  
    // TLM-2.0 Target Socket synthesized from extracted register tables  
    tlm\_utils::simple\_target\_socket\<dma\_controller\> reg\_socket;

    // Registers extracted from section\_03\_dma\_controller\_table\_001.csv  
    uint32\_t control\_reg;   // Bit 0: Enable, Bit 1: IE  
    uint32\_t source\_addr;   // Bits \[31:0\]: Source Address  
    uint32\_t dest\_addr;     // Bits \[31:0\]: Destination Address

    // Thread process synthesized from narrative prose in section\_03\_dma\_controller.md  
    void dma\_transfer\_process() {  
        while (true) {  
            wait(ev\_trigger);  
            if (control\_reg & 0x01) {  
                // Transfer logic implemented per specification text  
            }  
        }  
    }

    SC\_CTOR(dma\_controller) : reg\_socket("reg\_socket") {  
        SC\_THREAD(dma\_transfer\_process);  
    }  
};

### **Module Boundary Generation**

Top-level section headers (\# Section Header) delineate primary hardware sub-blocks, such as dma\_controller, interrupt\_controller, or bus\_bridge1. Sub-headers (\#\# or \#\#\#) define internal functional behaviors, such as state machines (SC\_METHOD), background processing loops (SC\_THREAD), or register control logic within the corresponding sc\_module8.

### **Register Map Ingestion**

Extracted CSV files stored in ./assets/tables/ contain structured register fields, bit offsets, access rights (Read/Write, Read-Only), and default reset values. Automated generation scripts parse these CSV files to create SystemC Transaction-Level Modeling (TLM-2.0) target sockets and register bank classes, connecting hardware address spaces directly to simulation memory maps1.

### **Top-Level Simulation Integration**

The generated manifest file (parsing\_manifest.json) provides a full structural index of the original document1. Downstream synthesis tools read this manifest to instantiate each extracted hardware component within a top-level SystemC simulation harness (sc\_main), automatically binding interconnect sockets based on the spec's defined module ordering and bus topologies.

## **Operational Deployment and Edge-Case Mitigation**

Deploying this document parsing pipeline across diverse hardware specification files requires managing several edge cases inherent to technical documentation1.

### **Filtering Small Graphical Elements**

By default, Docling ignores images covering less than 5% of a page's total area13. However, hardware documentation often includes small functional diagrams, logic gate symbols, or timing wave icons that fall below this threshold1. To ensure no relevant figures are lost, configure min\_picture\_page\_surface\_ratio \= 0.0 within PdfPipelineOptions13.

### **OCR Processing for Scanned Manuals**

Legacy specification documents or vendor datasheets may consist of scanned images rather than vector PDFs1. In these scenarios, integrate an optical character recognition engine like EasyOCR or Tesseract by defining do\_ocr \= True and setting force\_full\_page\_ocr \= True in the pipeline configuration13. This enforces visual line identification and text extraction across rasterized pages13.

### **Processing Large Specification Suites**

For architectural documents exceeding 500 pages, load the entire file into memory at once can exhaust system resources14. Optimize processing by specifying page ranges (page\_range \= (1, 50)) or using Docling's convert\_all interface to process document chunks in parallel across multiple CPU worker threads7.

#### **Works cited**

> 1. Docling AI: A Complete Guide to Parsing \- Codecademy, [https://www.codecademy.com/article/docling-ai-a-complete-guide-to-parsing](https://www.codecademy.com/article/docling-ai-a-complete-guide-to-parsing)  
> 2. Docling, [https://docling.ai/](https://docling.ai/)  
> 3. marker-pdf 1.0.0 \- PyPI, [https://pypi.org/project/marker-pdf/1.0.0/](https://pypi.org/project/marker-pdf/1.0.0/)  
> 4. docling-project/docling-parse: Simple package to extract text with coordinates from programmatic PDFs \- GitHub, [https://github.com/docling-project/docling-parse](https://github.com/docling-project/docling-parse)  
> 5. docling-project/docling: Get your documents ready for gen AI \- GitHub, [https://github.com/docling-project/docling](https://github.com/docling-project/docling)  
> 6. docling-project/docling-ibm-models \- GitHub, [https://github.com/docling-project/docling-ibm-models](https://github.com/docling-project/docling-ibm-models)  
> 7. Export figures \- Docling \- GitHub Pages, [https://docling-project.github.io/docling/\_generated/examples/export\_figures/](https://docling-project.github.io/docling/_generated/examples/export_figures/)  
> 8. Mastering Modern Hiring Demonstration: Using Docling and PostgreSQL by Bob to Build a Local Candidate RAG Database \- Medium, [https://alain-airom.medium.com/mastering-modern-hiring-demonstration-using-docling-and-postgresql-by-bob-to-build-a-local-4735ceedeb4b](https://alain-airom.medium.com/mastering-modern-hiring-demonstration-using-docling-and-postgresql-by-bob-to-build-a-local-4735ceedeb4b)  
> 9. GitHub \- datalab-to/marker: Convert PDF to markdown \+ JSON quickly with high accuracy, [https://github.com/datalab-to/marker](https://github.com/datalab-to/marker)  
> 10. PaperToSlides/README.md at main · jxtse/PaperToSlides · GitHub, [https://github.com/jxtse/PaperToSlides/blob/main/README.md](https://github.com/jxtse/PaperToSlides/blob/main/README.md)  
> 11. PyMuPDF4LLM, [https://pymupdf.io/4llm](https://pymupdf.io/4llm)  
> 12. Index \- Docling \- GitHub Pages, [https://docling-project.github.io/docling/](https://docling-project.github.io/docling/)  
> 13. Extract Content from Images · Issue \#1878 · docling-project/docling \- GitHub, [https://github.com/docling-project/docling/issues/1878](https://github.com/docling-project/docling/issues/1878)  
> 14. Docling Technical Report \- arXiv, [https://arxiv.org/html/2408.09869v5](https://arxiv.org/html/2408.09869v5)  
> 15. docling 1.17.0 \- PyPI, [https://pypi.org/project/docling/1.17.0/](https://pypi.org/project/docling/1.17.0/)  
> 16. Using Docling's OCR features with RapidOCR \- DEV Community, [https://dev.to/aairom/using-doclings-ocr-features-with-rapidocr-29hd](https://dev.to/aairom/using-doclings-ocr-features-with-rapidocr-29hd)  
> 17. pitapo/surya \- Hugging Face, [https://huggingface.co/pitapo/surya](https://huggingface.co/pitapo/surya)  
> 18. docling-core/docling\_core/transforms/chunker/hierarchical\_chunker.py at main \- GitHub, [https://github.com/DS4SD/docling-core/blob/main/docling\_core/transforms/chunker/hierarchical\_chunker.py](https://github.com/DS4SD/docling-core/blob/main/docling_core/transforms/chunker/hierarchical_chunker.py)  
> 19. Picture annotation with Docling \- Medium, [https://alain-airom.medium.com/picture-annotation-with-docling-b4b063b5f18c](https://alain-airom.medium.com/picture-annotation-with-docling-b4b063b5f18c)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAaCAYAAABCfffNAAABN0lEQVR4Xu2UsUoDURRER7GRgGhnqVb6AcHCwsLGThAr8wd+gY2FhaB1sLJZtbAT7ARBRWy0iJ1/EAQbtQkEEZ3JfYgZkuCGpNsDA8s9b+9d9u1boKCALDFXzAfzzTSYO2aVGWEumefkvphH5qB1Zx+cIxrNuiCbCLftIg964lem5iJxihhSdpGHRUSTfRdkjHlnXphRc7nYQQxZcUGWEe7MRV600WrUK1u/q/tgEtHk2kXiFuEXrC7mmHUvdmID0WTXBSkhPtu61aeZQ8QDZG2mC1rcbT/WEO7IRUJ7mXmxEzpoTWbcBakihlRcJP41ZB7R5MZF4gnhp1wkeg7RuXhgPhFN9M71a9Er01m4YN6SU+T2Wne2oyHHXhw0GnLixUGjIfrlDIUJxIB7xIej65m/CwoKhscPZ4pJy4rE2zwAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABkAAAAaCAYAAABCfffNAAABU0lEQVR4Xu2UPShFYRyHf6Tkq9gtNopRkkQpGZRF3aJkZjWQjzIoZillY7Apm5KPLGJgYrBLWTBQkvj97//t3nN/J7fO6drOU0/d8z7nvOd03vNeICOD9NFj+kZ/6Ae9oCO0ih7R+9C+6TXdyF+ZggP4RG0ayAS8zWtIgj3xM73RENiD36RbQxJ64JOsayA19JU+0WppiViG32RIAxmAt30NSbGFtonKOVM4OwXN8ElONQTO4b1DxlfgX+UVHZYWYxw+yaoG0gD/bB9lfIouht+99JN2FnOcLfy9HmPwtiPjC/QycvxAlyLHMWyj2ZPUaSCb8JtMaohQS9/ptIwXaIdPcqYhcAvvLRoizNI7Wq/B9oUt2Bd8Envntoj2ymwvHNKX0Exra/krS+miJ7RVQ6VopLu0KRwPFlNlsL+hbToKnzyHMmuSljnEN2t/yRkZGf/GL1vJUBnYI0UdAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,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>