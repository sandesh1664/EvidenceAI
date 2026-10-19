from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.datastructures import UploadFile
from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.document import DocumentResponse
from app.services import document_service
from app.services.document_storage import DocumentStorage, get_document_storage

router = APIRouter(prefix='/api/v1/workspaces/{workspace_id}/documents', tags=['documents'])


@router.post('/', response_model=DocumentResponse, status_code=202, openapi_extra={
    'requestBody': {'required': True, 'content': {'multipart/form-data': {'schema': {
        'type': 'object', 'required': ['file'], 'properties': {'file': {'type': 'string', 'format': 'binary'}}}}}}})
async def upload(workspace_id: UUID, request: Request, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
                 storage: DocumentStorage = Depends(get_document_storage)):
    actor_id = user.id
    await run_in_threadpool(document_service.authorize_upload, db, workspace_id, actor_id)
    async with request.form(max_files=1, max_fields=0, max_part_size=65536) as form:
        if list(form.keys()) != ['file'] or not isinstance(form.get('file'), UploadFile):
            raise HTTPException(422, 'Exactly one file field is required')
        return await run_in_threadpool(document_service.upload_document,db,workspace_id,actor_id,
                                       form['file'],settings,storage)


@router.get('/', response_model=list[DocumentResponse])
def list_documents(workspace_id: UUID, limit: int = Query(default=50,ge=1,le=100),
                   offset: int = Query(default=0,ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return document_service.list_documents(db,workspace_id,user.id,limit,offset)


@router.get('/{document_id}',response_model=DocumentResponse)
def read_document(workspace_id: UUID, document_id: UUID, user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    return document_service.read_document(db,workspace_id,document_id,user.id)


@router.get('/{document_id}/download')
def download(workspace_id: UUID,document_id: UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db),
             storage: DocumentStorage = Depends(get_document_storage)):
    document, stream = document_service.open_download(db,workspace_id,document_id,user.id,storage)
    def contents():
        try:
            while data := stream.read(65536):
                yield data
        finally:
            stream.close()
    from os import fstat
    headers = {'Content-Disposition': 'attachment; filename="document"; filename*=UTF-8\'\''+
               quote(document.original_filename,safe=''), 'X-Content-Type-Options':'nosniff',
               'Content-Length':str(fstat(stream.fileno()).st_size)}
    return StreamingResponse(contents(),media_type='application/octet-stream',headers=headers,
                             background=BackgroundTask(stream.close))


@router.delete('/{document_id}',status_code=204)
def delete_document(workspace_id: UUID,document_id: UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    document_service.delete_document(db,workspace_id,document_id,user.id)


@router.post('/{document_id}/retry',response_model=DocumentResponse,status_code=202)
def retry_document(workspace_id: UUID,document_id: UUID,user: User = Depends(get_current_user),db: Session = Depends(get_db),
                   settings: Settings = Depends(get_settings)):
    return document_service.retry_document(db,workspace_id,document_id,user.id,settings)
