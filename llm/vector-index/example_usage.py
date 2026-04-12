import os
from vectorless_index import LocalPageIndex

def generate_mock_pdf(filename: str):
    """
    Generate a simple mock technical manual PDF for testing.
    Needs reportlab installed (`pip install reportlab`).
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        print("Please install reportlab to generate the mock PDF: pip install reportlab")
        return

    c = canvas.Canvas(filename, pagesize=letter)
    
    # Page 1: Chapter 1
    c.setFont("Helvetica-Bold", 20)
    c.drawString(72, 700, "1. System Introduction")
    c.setFont("Helvetica", 12)
    c.drawString(72, 670, "The Vectorless architecture eliminates the need for vector databases.")
    c.drawString(72, 650, "It uses reasoning and hierarchical document structure instead.")
    c.showPage()
    
    # Page 2: Chapter 2
    c.setFont("Helvetica-Bold", 20)
    c.drawString(72, 700, "2. Setup and Configuration")
    c.setFont("Helvetica", 12)
    c.drawString(72, 670, "To configure the system, set the OPENAI_API_KEY environment variable.")
    c.drawString(72, 650, "Then initialize the LocalPageIndex object with your credentials.")
    c.showPage()
    
    # Page 3: Chapter 3
    c.setFont("Helvetica-Bold", 20)
    c.drawString(72, 700, "3. Troubleshooting")
    c.setFont("Helvetica", 12)
    c.drawString(72, 670, "If you encounter an API error 401, check your API key.")
    c.drawString(72, 650, "If parsing fails, ensure that 'docling' is correctly installed in your venv.")
    c.showPage()
    
    c.save()
    print(f"Generated mock PDF at {filename}")

if __name__ == "__main__":
    import base64
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Please set OPENAI_API_KEY environment variable.")
        exit(1)
        
    pdf_filename = "/home/ankdesh/Downloads/NVM-Express-2.3-Ratified-TPs-08012025-1/TP4215 Adding Reclaim Unit Handle Scope Reporting 2026.02.23 Ratified.pdf"
        
    print("--------------------------------------------------")
    print("Initializing Vectorless PageIndex App...")
    # Initialize the app
    index_app = LocalPageIndex(openai_api_key=api_key)
    
    # 1. Parse PDF using Docling and summarize sections
    print(f"\n--- STEP 1: PARSING AND SUMMARIZING ---\nFile: {pdf_filename}")
    try:
        index_app.parse_pdf(pdf_filename)
    except RuntimeError as e:
        print(f"Failed: {e}")
        exit(1)
    
    # 2. Traverse Index Structure
    print("\n--- STEP 2: TRAVERSING INDEX ---")
    index_app.traverse_index()
    
    # 3. Query the Index
    print("\n--- STEP 3: REASONING-BASED QUERY ---")
    queries = [
        "What is the purpose of the Reclaim Unit Handle?",
        "Are there any changes to the Identify Controller data structure?",
        "What chapters or sections talk about the new scope reporting?"
    ]
    
    for q in queries:
        print(f"\nQUERY: '{q}'")
        result = index_app.query_index(q)
        if "error" in result:
            print(f"Error reasoning: {result['error']}")
        else:
            print(f"Node reasoning: {result['thinking']}")
            print(f"Selected Node ID: {result['selected_node_id']}")
            print(f"Relevant Text extracted: \n{result['associated_text'][:500]}... [truncated]")

