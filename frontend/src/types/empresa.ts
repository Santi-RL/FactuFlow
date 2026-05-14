export interface Empresa {
  id: number;
  razon_social: string;
  cuit: string;
  condicion_iva: "RI" | "Monotributo" | "Exento";
  ingresos_brutos: string | null;
  domicilio: string;
  localidad: string;
  provincia: string;
  codigo_postal: string;
  email: string | null;
  telefono: string | null;
  inicio_actividades: string;
  logo: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmpresaCreate {
  razon_social: string;
  cuit: string;
  condicion_iva: "RI" | "Monotributo" | "Exento";
  ingresos_brutos?: string;
  domicilio: string;
  localidad: string;
  provincia: string;
  codigo_postal: string;
  email?: string;
  telefono?: string;
  inicio_actividades: string;
  logo?: string;
}

export interface EmpresaUpdate {
  razon_social?: string;
  cuit?: string;
  condicion_iva?: "RI" | "Monotributo" | "Exento";
  ingresos_brutos?: string;
  domicilio?: string;
  localidad?: string;
  provincia?: string;
  codigo_postal?: string;
  email?: string;
  telefono?: string;
  inicio_actividades?: string;
  logo?: string;
}

export interface ConstanciaArcaExtracted {
  razon_social: string | null;
  cuit: string | null;
  condicion_iva: Empresa["condicion_iva"] | null;
  domicilio: string | null;
  localidad: string | null;
  provincia: string | null;
  codigo_postal: string | null;
  inicio_actividades: string | null;
  warnings: string[];
}
