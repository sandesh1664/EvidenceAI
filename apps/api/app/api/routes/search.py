from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import User
from app.schemas.search import SearchRequest, SearchResult, IndexRequest, IndexStatus
from app.services import search_service, embedding_jobs

router = APIRouter(prefix='/api/v1/workspaces/{workspace_id}',tags=['retrieval'])


@router.post('/search',response_model=list[SearchResult])
def search(workspace_id: UUID,data: SearchRequest,user: User = Depends(get_current_user),
           db: Session = Depends(get_db),settings: Settings = Depends(get_settings)):
    return search_service.search(db,workspace_id,user.id,data,settings)


@router.get('/documents/{document_id}/index',response_model=IndexStatus)
def index_status(workspace_id: UUID,document_id: UUID,user: User = Depends(get_current_user),
                 db: Session = Depends(get_db),settings: Settings = Depends(get_settings)):
    return embedding_jobs.status(db,workspace_id,document_id,user.id,settings)


@router.post('/documents/{document_id}/index',response_model=IndexStatus,status_code=202)
def index_document(workspace_id: UUID,document_id: UUID,data: IndexRequest,
                   user: User = Depends(get_current_user),db: Session = Depends(get_db),settings: Settings = Depends(get_settings)):
    return embedding_jobs.request_index(db,workspace_id,document_id,user.id,settings,force=data.force)


@router.post('/documents/{document_id}/index/retry',response_model=IndexStatus,status_code=202)
def retry_index(workspace_id: UUID,document_id: UUID,user: User = Depends(get_current_user),
                db: Session = Depends(get_db),settings: Settings = Depends(get_settings)):
    return embedding_jobs.request_index(db,workspace_id,document_id,user.id,settings,retry=True)


@router.get('/research-status')
def research_status(workspace_id: UUID, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    from app.services.research_readiness import workspace_status
    return workspace_status(db, workspace_id, user.id, settings)
