"""
Restaurant Menu PDF ETL Jobs
Complete flow: PDF → Gemini → ETL Pipeline → Products
"""
from dagster import graph, Out, op, Field, String, In
import pandas as pd

# Existing imports
from ops.restaurant_menu_pdf_v1.extract_pdf_from_blob import extract_pdf_from_blob
from ops.restaurant_menu_pdf_v1.extract_menu_with_gemini_op import extract_menu_with_gemini_op
from ops.data2batches import load_in_batches


# ============================================================================
# SIMPLE TEST - GEMINI EXTRACTION ONLY
# ============================================================================

@op(
    config_schema={
        "pdf_path": Field(String, default_value="input/PNF-Food-Drinks.pdf"),
    }
)
def pick_pdf_for_test(context) -> str:
    """Pick a local PDF file for testing"""
    import os
    pdf_path = context.op_config["pdf_path"]
    
    context.log.info(f"📄 Selected PDF: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    return pdf_path


@graph(name="test_gemini_extraction_simple")
def test_gemini_extraction_simple():
    """Simple test - just extract menu with Gemini"""
    pdf_path = pick_pdf_for_test()
    menu_df = extract_menu_with_gemini_op(pdf_path)
    return menu_df


# ============================================================================
# LOCAL TESTING - COMPLETE ETL
# ============================================================================

@op(
    config_schema={
        "pdf_path": Field(String, default_value="input/PNF-Food-Drinks.pdf"),
        "business_account_id": Field(String),
        "batch_size": Field(int, default_value=5)
    },
    out={
        "pdf_path": Out(str),
        "business_id": Out(str),
        "batch_size": Out(int)
    }
)
def setup_local_test(context):
    """Setup local test with business account verification"""
    import os
    from services.business_account_service import get_business_details, resolve_industry_type
    
    pdf_path = context.op_config["pdf_path"]
    business_id = context.op_config["business_account_id"]
    batch_size = context.op_config.get("batch_size", 5)
    
    context.log.info(f"📄 PDF Path: {pdf_path}")
    context.log.info(f"🏢 Business ID: {business_id}")
    context.log.info(f"📦 Batch Size: {batch_size}")
    
    # Verify PDF exists
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Verify business account
    try:
        details = get_business_details(business_id)
        industry = resolve_industry_type(details.get('industry_type'))
        
        context.log.info(f"✓ Business Name: {details.get('name')}")
        context.log.info(f"✓ Industry Type: {industry}")
        
        if industry != 'restaurant':
            context.log.warning(f"⚠️  Business is '{industry}', not 'restaurant'")
    except Exception as e:
        raise ValueError(f"Invalid business_account_id: {e}")
    
    return pdf_path, business_id, batch_size


@op
def extract_menu_local(context, pdf_path: str):
    """Extract menu from local PDF using Gemini"""
    context.log.info(f"Extracting menu from: {pdf_path}")
    return extract_menu_with_gemini_op(context, pdf_path)


@op
def run_etl_pipeline(context, menu_df, business_id: str, batch_size: int):
    """Run complete ETL pipeline"""
    import asyncio
    
    context.log.info(f"Starting ETL for {len(menu_df)} menu items")
    context.log.info(f"Business ID: {business_id}")
    context.log.info(f"Batch Size: {batch_size}")
    
    result = asyncio.run(load_in_batches(
        context,
        df=menu_df,
        container_name=business_id,
        batch_size=batch_size
    ))
    
    context.log.info("✓ ETL Pipeline Complete")
    return result


@graph(name="test_local_full_etl")
def test_local_full_etl():
    """
    Test complete ETL with local PDF
    
    Flow:
    1. Setup and verify business account
    2. Extract menu with Gemini
    3. Run through complete ETL pipeline
    """
    pdf_path, business_id, batch_size = setup_local_test()
    menu_df = extract_menu_local(pdf_path)
    run_etl_pipeline(menu_df, business_id, batch_size)


@graph(name="test_gemini_only")
def test_gemini_only():
    """Test only Gemini extraction with business verification"""
    pdf_path, business_id, batch_size = setup_local_test()
    menu_df = extract_menu_local(pdf_path)
    return menu_df


# ============================================================================
# PRODUCTION - FROM BLOB STORAGE
# ============================================================================

@op(
    config_schema={
        "container_name": Field(String, description="Business account ID / container name"),
        "pdf_blob_name": Field(String, default_value="menu.pdf"),
        "batch_size": Field(int, default_value=10)
    },
    out={
        "container": Out(str),
        "blob_name": Out(str),
        "batch_size": Out(int)
    }
)
def get_production_config(context):
    """Get production ETL configuration"""
    container = context.op_config["container_name"]
    blob_name = context.op_config.get("pdf_blob_name", "menu.pdf")
    batch_size = context.op_config.get("batch_size", 10)
    
    context.log.info(f"🍽️  Production Restaurant ETL")
    context.log.info(f"  Container (Business ID): {container}")
    context.log.info(f"  PDF Blob Name: {blob_name}")
    context.log.info(f"  Batch Size: {batch_size}")
    
    return container, blob_name, batch_size


@op
def download_from_blob(context, container: str, blob_name: str) -> str:
    """Download PDF from Azure Blob Storage"""
    context.log.info(f"Downloading {blob_name} from container {container}")
    return extract_pdf_from_blob(context, container_name=container, blob_name=blob_name)


@op
def extract_menu_from_blob(context, pdf_path: str):
    """Extract menu from downloaded PDF"""
    context.log.info(f"Extracting menu from downloaded PDF: {pdf_path}")
    return extract_menu_with_gemini_op(context, pdf_path)


@op
def run_production_etl(context, menu_df, container: str, batch_size: int):
    """Run production ETL pipeline"""
    import asyncio
    
    context.log.info(f"Running production ETL")
    context.log.info(f"  Menu Items: {len(menu_df)}")
    context.log.info(f"  Business ID: {container}")
    context.log.info(f"  Batch Size: {batch_size}")
    
    result = asyncio.run(load_in_batches(
        context,
        df=menu_df,
        container_name=container,
        batch_size=batch_size
    ))
    
    context.log.info("✓ Production ETL Complete")
    return result


@graph(name="restaurant_production_etl")
def restaurant_production_etl():
    """
    Production Restaurant ETL Pipeline
    
    Flow:
    1. Get config (business_account_id from blob event)
    2. Download PDF from Azure Blob Storage
    3. Extract menu with Gemini
    4. Run complete ETL pipeline
    5. Create products and index to Elasticsearch
    """
    container, blob_name, batch_size = get_production_config()
    pdf_path = download_from_blob(container, blob_name)
    menu_df = extract_menu_from_blob(pdf_path)
    run_production_etl(menu_df, container, batch_size)
