from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.util.config import get_config_value
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler

from backend.api.router import router

from backend.lib.exceptions import (
    account_not_found_exception_handler,
    account_already_exists_exception_handler,
    database_error_exception_handler,
    generic_exception_handler
)
from backend.lib.exceptions import (
    AccountNotFoundError,
    AccountAlreadyExistsError,
    DatabaseError
)
from backend.util.config import get_config
from backend.util.log_setup import SetupLogging
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
import os 

logger = SetupLogging()
limiter = Limiter(key_func=get_remote_address)

secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
jwt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # INITIAL ROUTINES
    yield
    # CLOSING ROUTINES

# handle static files
if get_config_value("STATIC") == "true":
    class SPAStaticFilesMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            if response.status_code == 404 and request.url.path.startswith('/opsloom'):
                return FileResponse(os.path.join('public', 'opsloom', 'index.html'))
            return response

def create_app():
    # Load config
    config = get_config()
    print(config.keys())
    appname = config['app.config']['name']
    logger.info(f'!!! Staring App: {appname} !!!')
    allowed_origins_str = config.get('domains', 'allowed_origins', fallback='')
    allowed_origins_list = [origin.strip() for origin in allowed_origins_str.split(',') if origin.strip()]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=allowed_origins_list, 
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*']
        )
    ]
    
    app = FastAPI(
        title="LIL Rag API",
        version="1.0.0",
        docs_url="/docs",
        description="Generic API for Chatbot",
        lifespan=lifespan,
        middleware=middleware
    )

    # logfire.instrument_fastapi(app)

     # Add static file serving if the public/opsloom directory exists
    if os.path.exists(os.path.join(os.getcwd(), 'public', 'opsloom')):
        app.mount(
            "/opsloom",
            StaticFiles(directory="public/opsloom", html=True),
            name="opsloom"
        )

        

    # exception handlers 
    app.add_exception_handler(AccountNotFoundError, account_not_found_exception_handler)
    app.add_exception_handler(AccountAlreadyExistsError, account_already_exists_exception_handler)
    app.add_exception_handler(DatabaseError, database_error_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


    # Defined in /api/router.py
    app.include_router(router)

    
    app.state.limiter = limiter
    if get_config_value("STATIC") == "true":
        app.add_middleware(SPAStaticFilesMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # app.add_middleware(SlowAPIMiddleware)

    @app.get("/")
    async def root():
        return RedirectResponse(url='/opsloom')
    
    # return generic message instead of ugly Pydantic error when user sends malformed JSON
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=jsonable_encoder({
                "detail": "Invalid request body",
            })
        )

    @app.get("/ping")
    async def ping():
        return JSONResponse(status_code=200, content={"message": "pong"})
    
    return app
