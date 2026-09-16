import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Set up paths so we can import app modules
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.metadata.vector import local_vdb
from app.privacy.schemas import PrivacyAnalysisRequest
from app.privacy.service import analyze_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_offline_analysis():
    """
    Offline Cloud Content Analysis Pipeline
    As defined in Section V-B of the paper.
    Periodically reviews files stored in the cloud (synced by sync_drive.py),
    performs semantic vectorization, and pre-computes privacy baselines.
    """
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGO_DB_NAME", "saas_monitor")
    
    if not mongo_uri:
        logger.error("MONGODB_URI not set. Offline analysis aborted.")
        return
        
    import certifi
    client = AsyncIOMotorClient(
        mongo_uri, 
        tlsCAFile=certifi.where(),
        tlsAllowInvalidCertificates=True
    )
    db = client[db_name]
    
    logger.info("Starting Offline Cloud Content Analysis...")
    
    try:
        # Fetch all synced files
        cursor = db.files.find({})
        files = await cursor.to_list(length=None)
        
        if not files:
            logger.info("No files found in database. Run sync_drive.py first.")
            return
            
        for f in files:
            file_id = f["file_id"]
            file_name = f.get("name", "")
            
            # 1. Semantic Metadata Vectorization (Section III-C / V-B)
            local_vdb.insert(file_id, file_name)
            logger.info(f"Vectorized metadata for file: {file_name}")
            
            # 2. Offline Privacy Pre-computation
            try:
                req = PrivacyAnalysisRequest(text=file_name, event_id=f"offline_{file_id}")
                finding = await analyze_text(req)
                logger.info(f"Offline privacy baseline established for {file_name}: {finding.category} (Score: {finding.sensitivity_score})")
                
                await db.offline_baselines.update_one(
                    {"file_id": file_id},
                    {"$set": {"privacy_score": finding.sensitivity_score, "category": finding.category}},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Failed offline analysis for {file_name}: {e}")
                
        logger.info("Offline Cloud Content Analysis Complete.")
        
    except Exception as e:
        logger.error(f"MongoDB Connection Error: {e}")
        logger.error("Your local network or VPN is blocking the SSL handshake to MongoDB Atlas.")
        logger.error("Please disconnect your VPN or try a different network to run the offline analysis.")
    
if __name__ == "__main__":
    asyncio.run(run_offline_analysis())
