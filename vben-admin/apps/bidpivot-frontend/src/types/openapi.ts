// AUTO-GENERATED from the BidPivot OpenAPI schema.
// Run `python scripts/generate-openapi-types.py` after changing API schemas.

export interface AgentTemplateUpdate {
  "name"?: (string) | null;
  "system_prompt"?: (string) | null;
  "is_active"?: (boolean) | null;
}

export interface AnalysisRequest {
  "analysis_type": string;
  "competitor_ids": string[];
}

export interface ApiResponse_DirectoryResponse {
  "code"?: number;
  "data"?: (DirectoryResponse) | null;
  "message"?: string;
}

export interface ApiResponse_DocumentDetailResponse {
  "code"?: number;
  "data"?: (DocumentDetailResponse) | null;
  "message"?: string;
}

export interface ApiResponse_DocumentListResponse {
  "code"?: number;
  "data"?: (DocumentListResponse) | null;
  "message"?: string;
}

export interface ApiResponse_DocumentResponse {
  "code"?: number;
  "data"?: (DocumentResponse) | null;
  "message"?: string;
}

export interface ApiResponse_NoneType {
  "code"?: number;
  "data"?: null;
  "message"?: string;
}

export interface ApiResponse_ProjectDetailResponse {
  "code"?: number;
  "data"?: (ProjectDetailResponse) | null;
  "message"?: string;
}

export interface ApiResponse_ProjectListResponse {
  "code"?: number;
  "data"?: (ProjectListResponse) | null;
  "message"?: string;
}

export interface ApiResponse_ProjectResponse {
  "code"?: number;
  "data"?: (ProjectResponse) | null;
  "message"?: string;
}

export interface ApiResponse_list_DirectoryResponse {
  "code"?: number;
  "data"?: (DirectoryResponse[]) | null;
  "message"?: string;
}

export interface ApiResponse_list_dict {
  "code"?: number;
  "data"?: (Record<string, unknown>[]) | null;
  "message"?: string;
}

export interface ApiResponse_object {
  "code"?: number;
  "data"?: (unknown) | null;
  "message"?: string;
}

export interface Body_create_analysis_api_v1_loss_analysis_post {
  "file": string;
  "project_id"?: (string) | null;
}

export interface Body_upload_document_api_v1_competitors_competitor_id_documents_post {
  "file": string;
  "title": string;
  "file_type_tag": string;
}

export interface Body_upload_file_api_v1_files_upload_post {
  "file": string;
  "project_id"?: (string) | null;
  "file_type"?: string;
}

export interface Body_upload_global_document_api_v1_knowledge_global_documents_upload_post {
  "file": string;
  "title": string;
  "directory_id": string;
}

export interface Body_upload_personal_document_api_v1_knowledge_personal_documents_upload_post {
  "file": string;
  "title": string;
  "directory_id": string;
}

export interface CompetitorCreate {
  "name": string;
  "industry"?: (string) | null;
  "description"?: (string) | null;
}

export interface CompetitorUpdate {
  "name"?: (string) | null;
  "industry"?: (string) | null;
  "description"?: (string) | null;
}

export interface ConversationRequest {
  "instruction": string;
  "selected_text"?: (string) | null;
  "current_html": string;
}

export interface DirectoryCreate {
  "name": string;
  "parent_id"?: (string) | null;
}

export interface DirectoryResponse {
  "id": string;
  "name": string;
  "scope": string;
  "parent_id": (string) | null;
  "created_at": string;
}

export interface DocumentDetailResponse {
  "id": string;
  "title": string;
  "file_type": string;
  "status": string;
  "directory_id": string;
  "scope": string;
  "created_at": string;
  "updated_at": string;
  "content_text"?: (string) | null;
  "published_content_text"?: (string) | null;
  "published_at"?: (string) | null;
}

export interface DocumentListResponse {
  "items": DocumentResponse[];
  "total": number;
}

export interface DocumentResponse {
  "id": string;
  "title": string;
  "file_type": string;
  "status": string;
  "directory_id": string;
  "scope": string;
  "created_at": string;
  "updated_at": string;
}

export interface HTTPValidationError {
  "detail"?: ValidationError[];
}

export interface LogoutRequest {
  "refresh_token"?: (string) | null;
}

export interface ModelConfigCreate {
  "type": "llm" | "embedding";
  "provider_name"?: string;
  "api_base": string;
  "api_key"?: string;
  "model_name": string;
  "parameters"?: (Record<string, unknown>) | null;
  "is_active"?: boolean;
}

export interface ModelConfigUpdate {
  "provider_name"?: (string) | null;
  "api_base"?: (string) | null;
  "api_key"?: (string) | null;
  "model_name"?: (string) | null;
  "parameters"?: (Record<string, unknown>) | null;
  "is_active"?: (boolean) | null;
}

export interface ProjectCreate {
  "title": string;
  "industry_tags"?: string[];
}

export interface ProjectDetailResponse {
  "id": string;
  "user_id": string;
  "title": string;
  "status": string;
  "industry_tags": string[];
  "content_html"?: (string) | null;
  "content_json"?: (Record<string, unknown>) | null;
  "created_at": string;
  "updated_at": string;
  "outline_json"?: (Record<string, unknown>) | null;
  "requirements_json"?: (Record<string, unknown>) | null;
  "full_document_json"?: (Record<string, unknown>) | null;
  "conversation_history"?: (Record<string, unknown>[]) | null;
  "check_report"?: (Record<string, unknown>) | null;
  "generation_task_id"?: (string) | null;
}

export interface ProjectListResponse {
  "items": ProjectResponse[];
  "total": number;
}

export interface ProjectResponse {
  "id": string;
  "user_id": string;
  "title": string;
  "status": string;
  "industry_tags": string[];
  "content_html"?: (string) | null;
  "content_json"?: (Record<string, unknown>) | null;
  "created_at": string;
  "updated_at": string;
}

export interface ProjectUpdatePublic {
  "title"?: (string) | null;
  "industry_tags"?: (string[]) | null;
}

export interface RefreshRequest {
  "refresh_token": string;
}

export interface SearchRequest {
  "query": string;
  "top_k"?: number;
}

export interface UserCreate {
  "username": string;
  "password": string;
}

export interface UserCreateAdmin {
  "username": string;
  "password": string;
  "role"?: string;
}

export interface UserLogin {
  "username": string;
  "password": string;
  "captcha_id": string;
  "captcha_code": string;
}

export interface UserResetPassword {
  "new_password"?: (string) | null;
}

export interface UserUpdateAdmin {
  "username"?: (string) | null;
  "role"?: (string) | null;
  "is_active"?: (boolean) | null;
}

export interface ValidationError {
  "loc": (string | number)[];
  "msg": string;
  "type": string;
  "input"?: string;
  "ctx"?: Record<string, unknown>;
}

export interface WsTicketRequest {
  "task_id": string;
  "project_id": string;
}

export interface app_schemas_document_DocumentUpdate {
  "content_html"?: (string) | null;
  "content_json"?: (Record<string, unknown>) | null;
}

export interface app_schemas_knowledge_DocumentUpdate {
  "title"?: (string) | null;
  "content_text"?: (string) | null;
}
