export interface Usuario {
  id: number;
  email: string;
  nombre: string;
  empresa_id: number | null;
  activo: boolean;
  es_admin: boolean;
  created_at: string;
  ultimo_login: string | null;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: Usuario;
}

export interface SetupData {
  email: string;
  password: string;
  nombre: string;
  empresa_id?: number;
}

export interface SetupStatus {
  setup_required: boolean;
}

export interface UsuarioAdminCreate {
  email: string;
  nombre: string;
  password: string;
  es_admin: boolean;
  activo: boolean;
  empresa_id?: number | null;
}

export interface UsuarioAdminUpdate {
  email?: string;
  nombre?: string;
  es_admin?: boolean;
  activo?: boolean;
  empresa_id?: number | null;
}

export interface UsuarioPasswordReset {
  password: string;
}
