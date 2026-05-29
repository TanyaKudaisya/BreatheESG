// ─── Enums ────────────────────────────────────────────────────────────────────

export enum SourceSystem {
  SAP = 'SAP',
  UTILITY = 'UTILITY',
  CONCUR = 'CONCUR',
}

export enum ApprovalStatus {
  PENDING = 'PENDING',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
}

export enum FlagType {
  ESTIMATED_READING = 'estimated_reading',
  MISSING_RECEIPT = 'missing_receipt',
  ZERO_PRICE = 'zero_price',
  BLANK_QUANTITY = 'blank_quantity',
  PENDING_APPROVAL = 'pending_approval',
  UNKNOWN_AIRPORT = 'unknown_airport',
  UNKNOWN_UNIT = 'unknown_unit',
  POTENTIAL_DUPLICATE = 'potential_duplicate',
}

export enum Severity {
  WARNING = 'WARNING',
  ERROR = 'ERROR',
}

export enum AuditEventType {
  CREATE = 'CREATE',
  UPDATE = 'UPDATE',
  APPROVE = 'APPROVE',
  REJECT = 'REJECT',
  LOCK = 'LOCK',
  UNLOCK = 'UNLOCK',
}

export enum UserRole {
  ANALYST = 'ANALYST',
  AUDITOR = 'AUDITOR',
  ADMIN = 'ADMIN',
}

// ─── Core Models ──────────────────────────────────────────────────────────────

export interface Tenant {
  id: string;
  name: string;
  code: string;
  created_at: string;
}

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface DataQualityFlag {
  id: string;
  emission_record_id: string;
  flag_type: FlagType;
  severity: Severity;
  message: string;
  field_name: string | null;
  is_resolved: boolean;
  resolved_at: string | null;
  resolved_by_user_id: string | null;
}

export interface AuditEvent {
  id: string;
  event_type: AuditEventType;
  emission_record_id: string;
  user_id: string;
  tenant_id: string;
  timestamp: string;
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  metadata: Record<string, unknown>;
}

export interface MonthlyAllocation {
  id: string;
  emission_record_id: string;
  year: number;
  month: number;
  allocated_quantity: number;
  unit: string;
}

export interface EmissionRecord {
  id: string;
  tenant_id: string;
  source_system: SourceSystem;
  ingestion_timestamp: string;
  original_filename: string | null;
  raw_data: Record<string, unknown>;
  transaction_date: string;
  location: string;
  fuel_type: string | null;
  original_quantity: number | null;
  original_unit: string | null;
  normalized_quantity: number | null;
  normalized_unit: string | null;
  scope: number | null;
  scope_category: number | null;
  approval_status: ApprovalStatus;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  is_locked: boolean;
  locked_at: string | null;
  locked_by_user_id: string | null;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  data_quality_flags: DataQualityFlag[];
  monthly_allocations?: MonthlyAllocation[];
}

// ─── API Request / Response Payloads ─────────────────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface EmissionRecordFilters {
  source_system?: SourceSystem;
  scope?: number;
  date_from?: string;
  date_to?: string;
  approval_status?: ApprovalStatus;
  has_flags?: boolean;
  page?: number;
  page_size?: number;
}

export interface EditEmissionRecordPayload {
  original_quantity?: number;
  original_unit?: string;
  transaction_date?: string;
  location?: string;
}

export interface ApproveRecordPayload {
  ids?: string[];
}

export interface RejectRecordPayload {
  reason: string;
  ids?: string[];
}

export interface ResolveFlagPayload {
  flag_id: string;
}

export interface IngestionResult {
  records_parsed: number;
  records_with_errors: number;
  records_ingested: number;
  errors: IngestionError[];
}

export interface IngestionError {
  row: number | null;
  field: string | null;
  message: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface EmissionFactors {
  [fuel_type: string]: number;
}

export interface UnitConversions {
  [unit_code: string]: {
    target_unit: string;
    factor: number;
  };
}

export interface ScopeOverridePayload {
  scope: number;
  scope_category: number | null;
  justification: string;
}
