from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import sys
import os
 
# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
router = APIRouter()
 
# DON'T initialize ActionChatAgent here - use delayed initialization
action_agent = None

def get_action_agent():
    """Lazy initialization of ActionChatAgent"""
    global action_agent
    if action_agent is None:
        try:
            logger.info("Initializing ActionChatAgent...")
            from agent_hub.action_chat_agent import ActionChatAgent
            action_agent = ActionChatAgent()
            logger.info("ActionChatAgent initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ActionChatAgent: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize ActionChatAgent: {str(e)}")
    return action_agent
 
@router.post("/extract-json", response_model=Dict[str, Any])
async def extract_json_from_documents(
    excel_file: UploadFile = File(..., description="Excel file containing attributes to extract"),
    pdf_file: UploadFile = File(..., description="PDF file to extract data from")
):
    """
    Extract insurance data from PDF based on attributes from Excel file
   
    **Process:**
    1. Load attributes from Excel file
    2. Extract and chunk PDF content using Azure Document Intelligence
    3. Embed chunks in vector database (ChromaDB)
    4. Extract values for each attribute using LLM
    5. Format and validate results as JSON
   
    **Returns:** Structured JSON with extracted insurance data
    """
    try:
        # Get the agent (lazy initialization)
        agent = get_action_agent()
        
        # Validate file types
        if not excel_file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="Excel file must be .xlsx or .xls format")
       
        if not pdf_file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF file must be .pdf format")
       
        # Read file contents
        excel_content = await excel_file.read()
        pdf_content = await pdf_file.read()
       
        # Validate file sizes
        if len(excel_content) == 0:
            raise HTTPException(status_code=400, detail="Excel file is empty")
       
        if len(pdf_content) == 0:
            raise HTTPException(status_code=400, detail="PDF file is empty")
       
        logger.info(f"Processing files: {excel_file.filename} ({len(excel_content)} bytes) and {pdf_file.filename} ({len(pdf_content)} bytes)")
       
        # Process documents
        result = await agent.process_insurance_documents(
            excel_content=excel_content,
            pdf_content=pdf_content,
            excel_filename=excel_file.filename,
            pdf_filename=pdf_file.filename
        )
       
        return JSONResponse(content=result)
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract_json_from_documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
 
@router.get("/status", response_model=Dict[str, Any])
async def get_processing_status():
    """
    Get current processing status and system information
   
    **Returns:** Current status of the extraction agent and vector database
    """
    try:
        agent = get_action_agent()
        status = agent.get_processing_status()
        return JSONResponse(content=status)
       
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")
 
@router.post("/query-data", response_model=Dict[str, Any])
async def query_extracted_data(
    query: str,
    extraction_result: Dict[str, Any]
):
    """
    Query extracted data using natural language
   
    **Parameters:**
    - **query**: Natural language question about the extracted data
    - **extraction_result**: The result from a previous extraction
   
    **Returns:** Answer to the query based on extracted data
    """
    try:
        agent = get_action_agent()
        result = agent.query_extracted_data(query, extraction_result)
        return JSONResponse(content=result)
       
    except Exception as e:
        logger.error(f"Error querying data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying data: {str(e)}")
 
@router.post("/compare-extractions", response_model=Dict[str, Any])
async def compare_multiple_extractions(
    extraction_results: List[Dict[str, Any]]
):
    """
    Compare multiple extraction results
   
    **Parameters:**
    - **extraction_results**: List of extraction results to compare
   
    **Returns:** Comparison report showing differences and similarities
    """
    try:
        if len(extraction_results) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 extraction results for comparison")
        
        agent = get_action_agent()
        result = agent.compare_extractions(extraction_results)
        return JSONResponse(content=result)
       
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing extractions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error comparing extractions: {str(e)}")
 
@router.get("/processing-history", response_model=Dict[str, Any])
async def get_processing_history(
    limit: int = Query(10, description="Number of recent processing records to return")
):
    """
    Get processing history
   
    **Parameters:**
    - **limit**: Number of recent records to return (default: 10)
   
    **Returns:** List of recent processing activities
    """
    try:
        agent = get_action_agent()
        result = agent.get_processing_history(limit)
        return JSONResponse(content=result)
       
    except Exception as e:
        logger.error(f"Error getting processing history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting processing history: {str(e)}")
 
@router.post("/validate-files", response_model=Dict[str, Any])
async def validate_input_files(
    excel_file: UploadFile = File(..., description="Excel file to validate"),
    pdf_file: UploadFile = File(..., description="PDF file to validate")
):
    """
    Validate input files before processing
   
    **Returns:** Validation results for both files
    """
    try:
        # Get the agent (lazy initialization)
        agent = get_action_agent()
        
        # Read file contents
        excel_content = await excel_file.read()
        pdf_content = await pdf_file.read()
       
        # Validate using agent handler
        validation_result = agent.agent_handler.validate_inputs(excel_content, pdf_content)
       
        # Add file information
        validation_result["file_info"] = {
            "excel_filename": excel_file.filename,
            "excel_size_bytes": len(excel_content),
            "pdf_filename": pdf_file.filename,
            "pdf_size_bytes": len(pdf_content)
        }
       
        return JSONResponse(content=validation_result)
       
    except Exception as e:
        logger.error(f"Error validating files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error validating files: {str(e)}")
 
@router.delete("/clear-data", response_model=Dict[str, Any])
async def clear_processing_data():
    """
    Clear vector database and processing history
   
    **Returns:** Confirmation of data clearing
    """
    try:
        agent = get_action_agent()
        result = agent.clear_processing_data()
        return JSONResponse(content=result)
       
    except Exception as e:
        logger.error(f"Error clearing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error clearing data: {str(e)}")
 
@router.get("/sample-attributes", response_model=Dict[str, Any])
async def get_sample_attributes():
    """
    Get sample attributes that can be extracted from insurance documents
   
    **Returns:** List of commonly extracted insurance attributes
    """
    try:
        sample_attributes = [
            "Total Insured Value",
            "Quoted Amount",
            "Limit Amount",
            "Limit per occurrence",
            "Attachment Point",
            "Annual Premium",
            "100 % Annual Premium",
            "Premium due",
            "100% layer premium w/o terrorism"
        ]
       
        attribute_descriptions = {
            "Total Insured Value": "The total value of all insured property and assets",
            "Quoted Amount": "The coverage limit or amount being quoted for insurance",
            "Limit Amount": "The maximum coverage limit per occurrence",
            "Limit per occurrence": "Maximum amount payable per single occurrence or event",
            "Attachment Point": "The excess amount or deductible where coverage begins",
            "Annual Premium": "The yearly premium amount for the insurance policy",
            "100 % Annual Premium": "The total 100% annual premium including all layers",
            "Premium due": "The premium amount due at policy inception",
            "100% layer premium w/o terrorism": "Total layer premium excluding terrorism coverage"
        }
       
        return JSONResponse(content={
            "success": True,
            "sample_attributes": sample_attributes,
            "attribute_descriptions": attribute_descriptions,
            "total_attributes": len(sample_attributes),
            "usage_note": "Create an Excel file with these attributes in the first column to extract their values from insurance PDFs"
        })
       
    except Exception as e:
        logger.error(f"Error getting sample attributes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting sample attributes: {str(e)}")
 
@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint
   
    **Returns:** API health status
    """
    return JSONResponse(content={
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Insurance Data Extraction API",
        "version": "1.0.0",
        "agent_initialized": action_agent is not None
    })