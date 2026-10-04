import sys
import os
from pathlib import Path
from uuid import UUID

sys.path.insert(0, os.path.dirname(__file__))

from backend.app.db.database import SessionLocal
from sqlalchemy import text
from backend.app.services.pdf_service import extract_pdf_text
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import upsert_asset_embedding

# Curated high-quality descriptions for brochures and documents
PDF_DESCRIPTIONS = {
    "residential_project_brochure_2024.pdf": "Brochure related to residential projects, luxury apartments, and residential developments. Features architectural floor plans, residential amenities, modern living spaces, pricing guide, and developer specifications.",
    "company_overview_brochure.pdf": "Corporate marketing brochure presenting company overview, mission statement, executive leadership, client portfolio, core enterprise capabilities, and professional business solutions.",
    "property_investment_guide.pdf": "Real estate property investment guide and brochure covering residential and commercial properties, market analysis, rental yield projections, financing options, and prime property listings.",
    "construction_project_report.pdf": "Construction project engineering report detailing site progress, structural inspections, contractor activities, building safety protocols, material logistics, and timeline milestones.",
    "engineering_technical_guidelines.pdf": "Technical engineering guidelines and design specifications for architectural planning, civil engineering standards, electrical schematics, and structural compliance.",
    "legal_constitution_document.pdf": "Official legal and governance constitution document detailing bylaws, compliance regulations, governance frameworks, and statutory legal requirements.",
    "mozilla_tracemonkey_research.pdf": "Academic research paper on JavaScript tracing JIT compilation, compiler optimizations, bytecode execution, and memory performance benchmarks.",
    "project_specifications_document.pdf": "Formal project specifications and technical requirements document covering system architecture, engineering deliverables, acceptance criteria, and project scope.",
    "sustainability_report_2024.pdf": "Annual corporate environmental sustainability and ESG report covering carbon footprint reduction, renewable energy initiatives, green building practices, and sustainability targets.",
    "urban_architecture_blueprints.pdf": "Urban architecture blueprints and design portfolio for modern residential and commercial buildings, structural layouts, zoning blueprints, and civic infrastructure.",
    "w3c_accessibility_guidelines.pdf": "Web Content Accessibility Guidelines (WCAG) technical reference documenting standards for accessible user interfaces, contrast requirements, screen reader support, and digital accessibility compliance.",
    "dummy_standard_test.pdf": "Standard sample test PDF document with formatted paragraphs, headings, bulleted lists, and basic text formatting for ingestion testing.",
    "sample1_document_text.pdf": "Sample text document with introductory business paragraphs and test content for indexing verification.",
    "sample2_multipage_report.pdf": "Multi-page business report document containing executive summary, data tables, and quarterly performance metrics.",
    "sample_academic_document.pdf": "Academic research document sample containing formal abstracts, methodology sections, citations, and scholarly literature review.",
    "orimi_pdf_test_reference.pdf": "Reference PDF test document containing standard typography, vector graphics, and layout structures for parser testing."
}

def main():
    db = SessionLocal()
    pdf_dir = Path("data/pdfs")
    
    try:
        rows = db.execute(text("SELECT id, filename, description FROM assets WHERE file_type = 'pdf'")).mappings().all()
        print(f"Found {len(rows)} PDF assets in DB")
        
        for r in rows:
            asset_id = str(r["id"])
            filename = r["filename"]
            pdf_path = pdf_dir / filename
            
            # Extract actual text if file exists
            extracted = ""
            if pdf_path.exists():
                try:
                    extracted = extract_pdf_text(pdf_path) or ""
                except Exception as e:
                    print(f"Error extracting text from {filename}: {e}")
            
            # Use curated description + first 300 chars of extracted text
            curated = PDF_DESCRIPTIONS.get(filename, f"Document and PDF brochure: {filename}")
            if extracted and len(extracted) > 50:
                final_desc = f"{curated} Content excerpt: {extracted[:300].strip()}"
            else:
                final_desc = curated
                
            # Update DB
            db.execute(
                text("""
                    UPDATE assets
                    SET description = :desc,
                        extracted_text = :ext,
                        status = 'indexed',
                        updated_at = NOW()
                    WHERE id = :id
                """),
                {
                    "desc": final_desc,
                    "ext": extracted,
                    "id": asset_id
                }
            )
            db.commit()
            
            # Re-embed into Qdrant
            vec = generate_embedding(final_desc)
            upsert_asset_embedding(
                UUID(asset_id),
                vec,
                filename=filename,
                file_type="pdf"
            )
            print(f"Updated {filename} -> {final_desc[:70]}")
            
        print("\nAll PDF assets re-indexed with semantic descriptions!")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
