import uvicorn
from backend.app import create_app
import logging
import dotenv

# Load env variables from .env file
dotenv.load_dotenv()

# Initialize the FastAPI app
app = create_app()
logging.info('RAG system initialized.')

if __name__ == "__main__":
    logging.info('Started Fast API server')
    uvicorn.run(app, host='0.0.0.0', port=8080)
