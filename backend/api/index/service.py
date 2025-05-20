import os
import uuid
from fastapi import HTTPException, UploadFile
from backend.api.index.upload_s3 import UploadS3
from backend.api.index.document_loader import DocumentLoader
from backend.api.index.text_processor import TextProcessor
from backend.api.kbase.services import KbaseService
from backend.api.kbase.repository import KbaseRepository
from backend.api.kbase.models import Document, Chunk
from backend.api.kbase.pgvectorstore import PostgresVectorStore
from backend.api.kbase.embedder_factory import get_embedder  # The embedder factory
from sqlalchemy.ext.asyncio import AsyncSession
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

class IndexService:
    def __init__(self, kbase_name: str, session: AsyncSession):
        self.kbase_name = kbase_name
        self.session = session  # Session is injected from the route
        self.s3_uploader = UploadS3()
        self.document_loader = DocumentLoader(kbase_name)
        self.text_processor = TextProcessor()
        # Create repository and kbase service using the provided session.
        self.kbase_repository = KbaseRepository(session)
        self.kbase_service = KbaseService(repository=self.kbase_repository)

    async def process_and_index_document(self, file: UploadFile, kbase_name: str) -> str:
        try:
            kbase = await self.kbase_service.get_kbase_by_name(kbase_name)
            if not kbase:
                raise HTTPException(status_code=404, detail="Knowledge base not found")

            # Upload file to S3.
            object_name = f"{kbase_name}/{file.filename}"
            if not await self.s3_uploader.upload_file(file, object_name):
                raise HTTPException(status_code=500, detail="Failed to upload file to S3")
            s3_uri = self.s3_uploader.get_s3_uri(object_name)

            # Load and process the document.
            raw_documents = self.document_loader.load_documents([s3_uri])
            split_docs = self.text_processor.split_documents(raw_documents)

            # Group split chunks into a single kbase Document.
            document = self._group_chunks_by_document_id(split_docs)

            # Create the embedder using the factory.
            embedder = get_embedder("openai", api_key=os.getenv("OPENAI_API_KEY"))

            # embedder = get_embedder("boto3", region_name=os.getenv("AWS_REGION"))

            # Compute embeddings for each chunk.
            for i, chunk in enumerate(document.chunks):
                updated_chunk = await embedder.embed_text(chunk)
                document.chunks[i].embeddings = updated_chunk.embeddings

            # Persist the document’s chunks to the vector store.
            vector_store = PostgresVectorStore(self.session, kbase_id=kbase.id)
            await vector_store.add_document(document)

            return s3_uri

        except HTTPException as http_ex:
            logger.error(f"HTTP error in process_and_index_document: {str(http_ex)}")
            raise
        except Exception as e:
            logger.error(f"Error in process_and_index_document: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    def _group_chunks_by_document_id(self, split_docs: list) -> Document:
        """
        Since we are processing a single uploaded document, group all split chunks into one Document.
        """
        from backend.api.kbase.models import Document
        chunks = []
        for doc in split_docs:
            # Generate a new UUID for each chunk.
            chunk_uuid = uuid.uuid4()
            chunk = Chunk(
                id=chunk_uuid,
                content=doc.page_content,
                embeddings=doc.metadata.get("embedding")  # Will be populated later.
            )
            chunks.append(chunk)
        # Return a single Document containing all chunks.
        return Document(chunks=chunks)