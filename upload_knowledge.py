"""
Script para subir documentos de conocimiento a Pinecone.
Uso: python upload_knowledge.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from rag import add_text_file, add_pdf, list_documents, delete_document


def main():
    print("=== Subir Documento de Conocimiento a Pinecone ===\n")

    docs_dir = os.path.dirname(os.path.abspath(__file__))

    md_file = os.path.join(docs_dir, "conocimiento_tusabogados.md")
    pdf_file = os.path.join(docs_dir, "conocimiento_tusabogados.pdf")

    print("Documentos actuales en Pinecone:")
    existing = list_documents()
    if existing:
        for doc in existing:
            print(f"  - {doc}")
    else:
        print("  (ninguno)")
    print()

    if existing:
        resp = input(
            "¿Desea eliminar los documentos existentes antes de subir? (s/n): "
        )
        if resp.lower() == "s":
            for doc in existing:
                ok, msg = delete_document(doc)
                print(f"  Eliminado: {msg}")

    if os.path.exists(pdf_file):
        print(f"\nSubiendo PDF: {pdf_file}")
        count, msg = add_pdf(pdf_file, source_name="conocimiento_tusabogados.pdf")
        print(f"  Resultado: {msg}")
    elif os.path.exists(md_file):
        print(f"\nSubiendo Markdown: {md_file}")
        count, msg = add_text_file(md_file, source_name="conocimiento_tusabogados.md")
        print(f"  Resultado: {msg}")
    else:
        print("\nNo se encontró ningún documento de conocimiento.")
        print(f"  Buscado: {pdf_file}")
        print(f"  Buscado: {md_file}")
        return

    print("\nDocumentos en Pinecone después de subir:")
    final_docs = list_documents()
    if final_docs:
        for doc in final_docs:
            print(f"  - {doc}")
    else:
        print("  (ninguno)")

    print("\nListo.")


if __name__ == "__main__":
    main()
