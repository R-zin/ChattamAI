# Plan: RAG System for Kerala Building Rules Compliance

## Context
This project aims to develop a RAG (Retrieval-Augmented Generation) system for Local Self-Government Department (LSGD) engineers in Kerala. The system will allow engineers to upload building plans provided by clients, compare them against the Kerala Building Rules (KBR), and identify potential violations.

## Scope
- Ingest and index Kerala Building Rules (PDFs/Text).
- Process uploaded building plans (likely PDF or image-based floor plans).
- Implement a RAG pipeline that retrieves relevant rules based on the plan details.
- Provide a summary of potential violations detected by the AI.

## Phase 1: Exploration
- Locate/upload Kerala Building Rules documents.
- Research existing Python tools for extracting information from floor plans.
- Identify suitable LLM/embedding models for legal/regulatory document RAG.

## Phase 2: Design
- Define the architecture:
    - Document loader and vector store for building rules.
    - Plan parser (OCR or layout analysis).
    - Prompt engineering to compare extracted facts with rules.

## Phase 3: Implementation
- Set up document ingestion.
- Develop the RAG query engine.
- Build the plan parsing logic.

## Verification
- Test with sample building plans and known rule references.
- Engineer review to ensure rule interpretation accuracy.
