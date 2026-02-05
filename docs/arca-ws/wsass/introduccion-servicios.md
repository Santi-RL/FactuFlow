# WSASS - Homologación

## Introducción

`	ext
TAREAS QUE SE PUEDEN HACER EN ESTE SITIO

En este sitio los programadores de aplicaciones pueden solicitar acceso a los diversos webservices (denominados "servicios") que están disponibles en el ambiente de testing/homologación de la AFIP. No son de aplicación para el ambiente de Producción.

Para poder acceder a un servicio, la aplicación a programar debe utilizar un certificado de seguridad, que se obtiene en este sitio. Entre otras cosas, el certificado contiene un Distinguished Name (DN) que incluye una CUIT. Cada DN será identificado por un "alias" o "nombre simbólico", que actúa como una abreviación.

Autoservicio de certificados

Para obtener el certificado, distinguimos dos casos según si el DN ya fué dado de alta (DN existente) o si aún no existe. Según sea el caso, utilice uno de los formularios siguientes:

Formulario para obtener el certificado por primera vez
Formulario para obtener otro certificado adicional (para un DN existente)
Tareas relacionadas:
Ver los certificados emitidos para una CUIT

Gestión de accesos a servicios

Una vez generado el DN y obtenido el certificado, se puede solicitar autorización de acceso a los servicios de AFIP.

Ver el catálogo de servicios disponibles
Formulario de solicitud de autorización de acceso a servicio
Tareas relacionadas:
Formulario para eliminar una autorización de acceso a servicio

Delegación de representación

Una vez obtenido el certificado, se puede delegar la representación mediante la opción del menú Crear autorización a servicio, donde en la opción “CUIT representado” se debe colocar el cuit a representar y además se debe seleccionar el Servicio deseado.

CÓMO GENERAR UNA SOLICITUD DE CERTIFICADO (CSR)

Para obtener el certificado por primera vez, hay que dar de alta al DN. Para esto hay que presentar una "solicitud de certificado" o "Certificate Signing Request" (CSR).

El CSR se genera en su computadora, usando la herramienta OpenSSL (disponible para Windows, UNIX/Linux y MacOSX). Se hace en dos pasos

primero hay que generar una clave privada en formato PKCS#10 con un mínimo de 2048 bits

openssl genrsa -out MiClavePrivada 2048

y segundo, generar el CSR. Para ello, la forma de ejecutar 'openssl' en la línea de comandos es así:

openssl req -new -key MiClavePrivada -subj "/C=AR/O=subj_o/CN=subj_cn/serialNumber=CUIT subj_cuit" -out MiPedidoCSR

donde hay que reemplazar

MiClavePrivada por nombre del archivo elegido en el primer paso.
subj_o por el nombre de su empresa
subj_cn por el nombre de su sistema cliente
subj_cuit por la CUIT (sólo los 11 dígitos, sin guiones) de la empresa o del programador (persona jurídica)
MiClavePrivada por el nombre del archivo de la clave privada generado antes
MiPedidoCSR por el nombre del archivo CSR que se va a crear
Por ejemplo para
una empresa llamada EmpresaPrueba
un sistema TestSystem
el cuit = 20123456789
con el archivo MiClavePrivada generado en el punto anterior:

openssl req -new -key MiClavePrivada -subj "/C=AR/O=EmpresaPrueba/CN=TestSystem/serialNumber=CUIT 20123456789" -out MiPedidoCSR

Si no hay errores, el archivo 'MiPedidoCSR' será utilizado al momento de obtener el DN y el certificado.

PARA MAS INFORMACIÓN
Referirse a www.afip.gob.ar/ws
ENLACES EXTERNOS DE INTERÉS
Sitio web para descargar OpenSSL
Estándares de criptografía de clave pública
Certificados X.509
`"
# WSASS - Homologación  ## Introducción  `	ext TAREAS QUE SE PUEDEN HACER EN ESTE SITIO  En este sitio los programadores de aplicaciones pueden solicitar acceso a los diversos webservices (denominados "servicios") que están disponibles en el ambiente de testing/homologación de la AFIP. No son de aplicación para el ambiente de Producción.  Para poder acceder a un servicio, la aplicación a programar debe utilizar un certificado de seguridad, que se obtiene en este sitio. Entre otras cosas, el certificado contiene un Distinguished Name (DN) que incluye una CUIT. Cada DN será identificado por un "alias" o "nombre simbólico", que actúa como una abreviación.  Autoservicio de certificados  Para obtener el certificado, distinguimos dos casos según si el DN ya fué dado de alta (DN existente) o si aún no existe. Según sea el caso, utilice uno de los formularios siguientes:  Formulario para obtener el certificado por primera vez Formulario para obtener otro certificado adicional (para un DN existente) Tareas relacionadas: Ver los certificados emitidos para una CUIT  Gestión de accesos a servicios  Una vez generado el DN y obtenido el certificado, se puede solicitar autorización de acceso a los servicios de AFIP.  Ver el catálogo de servicios disponibles Formulario de solicitud de autorización de acceso a servicio Tareas relacionadas: Formulario para eliminar una autorización de acceso a servicio  Delegación de representación  Una vez obtenido el certificado, se puede delegar la representación mediante la opción del menú Crear autorización a servicio, donde en la opción “CUIT representado” se debe colocar el cuit a representar y además se debe seleccionar el Servicio deseado.  CÓMO GENERAR UNA SOLICITUD DE CERTIFICADO (CSR)  Para obtener el certificado por primera vez, hay que dar de alta al DN. Para esto hay que presentar una "solicitud de certificado" o "Certificate Signing Request" (CSR).  El CSR se genera en su computadora, usando la herramienta OpenSSL (disponible para Windows, UNIX/Linux y MacOSX). Se hace en dos pasos  primero hay que generar una clave privada en formato PKCS#10 con un mínimo de 2048 bits  openssl genrsa -out MiClavePrivada 2048  y segundo, generar el CSR. Para ello, la forma de ejecutar 'openssl' en la línea de comandos es así:  openssl req -new -key MiClavePrivada -subj "/C=AR/O=subj_o/CN=subj_cn/serialNumber=CUIT subj_cuit" -out MiPedidoCSR  donde hay que reemplazar  MiClavePrivada por nombre del archivo elegido en el primer paso. subj_o por el nombre de su empresa subj_cn por el nombre de su sistema cliente subj_cuit por la CUIT (sólo los 11 dígitos, sin guiones) de la empresa o del programador (persona jurídica) MiClavePrivada por el nombre del archivo de la clave privada generado antes MiPedidoCSR por el nombre del archivo CSR que se va a crear Por ejemplo para una empresa llamada EmpresaPrueba un sistema TestSystem el cuit = 20123456789 con el archivo MiClavePrivada generado en el punto anterior:  openssl req -new -key MiClavePrivada -subj "/C=AR/O=EmpresaPrueba/CN=TestSystem/serialNumber=CUIT 20123456789" -out MiPedidoCSR  Si no hay errores, el archivo 'MiPedidoCSR' será utilizado al momento de obtener el DN y el certificado.  PARA MAS INFORMACIÓN Referirse a www.afip.gob.ar/ws ENLACES EXTERNOS DE INTERÉS Sitio web para descargar OpenSSL Estándares de criptografía de clave pública Certificados X.509 += "
# WSASS - Homologación  ## Introducción  `	ext TAREAS QUE SE PUEDEN HACER EN ESTE SITIO  En este sitio los programadores de aplicaciones pueden solicitar acceso a los diversos webservices (denominados "servicios") que están disponibles en el ambiente de testing/homologación de la AFIP. No son de aplicación para el ambiente de Producción.  Para poder acceder a un servicio, la aplicación a programar debe utilizar un certificado de seguridad, que se obtiene en este sitio. Entre otras cosas, el certificado contiene un Distinguished Name (DN) que incluye una CUIT. Cada DN será identificado por un "alias" o "nombre simbólico", que actúa como una abreviación.  Autoservicio de certificados  Para obtener el certificado, distinguimos dos casos según si el DN ya fué dado de alta (DN existente) o si aún no existe. Según sea el caso, utilice uno de los formularios siguientes:  Formulario para obtener el certificado por primera vez Formulario para obtener otro certificado adicional (para un DN existente) Tareas relacionadas: Ver los certificados emitidos para una CUIT  Gestión de accesos a servicios  Una vez generado el DN y obtenido el certificado, se puede solicitar autorización de acceso a los servicios de AFIP.  Ver el catálogo de servicios disponibles Formulario de solicitud de autorización de acceso a servicio Tareas relacionadas: Formulario para eliminar una autorización de acceso a servicio  Delegación de representación  Una vez obtenido el certificado, se puede delegar la representación mediante la opción del menú Crear autorización a servicio, donde en la opción “CUIT representado” se debe colocar el cuit a representar y además se debe seleccionar el Servicio deseado.  CÓMO GENERAR UNA SOLICITUD DE CERTIFICADO (CSR)  Para obtener el certificado por primera vez, hay que dar de alta al DN. Para esto hay que presentar una "solicitud de certificado" o "Certificate Signing Request" (CSR).  El CSR se genera en su computadora, usando la herramienta OpenSSL (disponible para Windows, UNIX/Linux y MacOSX). Se hace en dos pasos  primero hay que generar una clave privada en formato PKCS#10 con un mínimo de 2048 bits  openssl genrsa -out MiClavePrivada 2048  y segundo, generar el CSR. Para ello, la forma de ejecutar 'openssl' en la línea de comandos es así:  openssl req -new -key MiClavePrivada -subj "/C=AR/O=subj_o/CN=subj_cn/serialNumber=CUIT subj_cuit" -out MiPedidoCSR  donde hay que reemplazar  MiClavePrivada por nombre del archivo elegido en el primer paso. subj_o por el nombre de su empresa subj_cn por el nombre de su sistema cliente subj_cuit por la CUIT (sólo los 11 dígitos, sin guiones) de la empresa o del programador (persona jurídica) MiClavePrivada por el nombre del archivo de la clave privada generado antes MiPedidoCSR por el nombre del archivo CSR que se va a crear Por ejemplo para una empresa llamada EmpresaPrueba un sistema TestSystem el cuit = 20123456789 con el archivo MiClavePrivada generado en el punto anterior:  openssl req -new -key MiClavePrivada -subj "/C=AR/O=EmpresaPrueba/CN=TestSystem/serialNumber=CUIT 20123456789" -out MiPedidoCSR  Si no hay errores, el archivo 'MiPedidoCSR' será utilizado al momento de obtener el DN y el certificado.  PARA MAS INFORMACIÓN Referirse a www.afip.gob.ar/ws ENLACES EXTERNOS DE INTERÉS Sitio web para descargar OpenSSL Estándares de criptografía de clave pública Certificados X.509 += 

Catálogo de servicios disponibles.
Actualmente hay 188 servicios disponibles en el catálogo.

| Acción | Id | Descripción | URL |
| --- | --- | --- | --- |
| Ver | arbccf | Alta, renovación y baja de certificados de controladores fiscales | https://wsaahomo.afip.gov.ar/controladores-fiscales-ws/CertificadosService/CertificadosBean |
| Ver | certservicios | Certificación de Servicios de los Recursos de la Seguridad Social | https://testdia.afip.gob.ar/diirss/certservicios/Service.asmx |
| Ver | consultaautorizacioneselectronicas | Consulta de cuits autorizados electronicamente | https://wsaduhomoext.afip.gob.ar/AutorizacionesElectronicas/AutorizacionesElectronicas.asmx |
| Ver | djprocessorcontribuyente | Permite que los contribuyentes presenten sus propias DDJJ en forma automática. | https://awshomo.afip.gov.ar/setiws/webservices/uploadPresentacionService |
| Ver | djprocessorcontribuyente_cf | Permite la presentación de DDJJ solo de formularios asociados a los Controladores Fiscales | https://awshomo.afip.gov.ar/setiws/webservices/uploadPresentacionService |
| Ver | dj-rapida-secindustria-api | dj-rapida-secindustria-api | https://dj-rapida-secindustria-api-qaext.afip.gob.ar/secindustria/ |
| Ver | dummy | Monitoreo | https://wsaahomo.afip.gov.ar/test/ |
| Ver | f1272-dj-vinculada-api | f1272-dj-vinculada-api | https://siapweb-f1272-dj-vinculada-api-qaext.afip.gob.ar/f1272-dj-vinculada/ |
| Ver | liqdigital-api | API REST liquidación de sueldo | https://webserviceshomoext.afip.gob.ar/liqdigital-api |
| Ver | miargentina-ws | WS MiArgentina | https://webserviceshomoext.afip.gob.ar/miargentina-ws/servicios.asmx |
| Ver | oconws | WS Osiris Concentrador Web | https://oconws-homoext.afip.gob.ar/concentrador/services/oconws |
| Ver | padron-puc-ws-consulta-nivel10 | Consulta PUC nivel 10 | https://awshomo.afip.gov.ar/padron-puc-ws/services/select.ContribuyenteNivel10SelectServiceImpl |
| Ver | padron-puc-ws-consulta-nivel3 | Consulta PUC nivel 3 | https://awshomo.afip.gov.ar/padron-puc-ws/services/select.ContribuyenteNivel3SelectServiceImpl |
| Ver | padron-puc-ws-consulta-nivel4 | WS de consulta PUC nivel 4 | https://awshomo.afip.gov.ar/padron-puc-ws/services/select.ContribuyenteNivel4SelectServiceImpl |
| Ver | presentacionprocessor | Permite que organismos externos presenten las DDJJ de sus contribuyentes en forma automática. | https://awshomo.afip.gov.ar/setiws/webservices/uploadPresentacionService |
| Ver | recibo-api | Liquidacion de sueldos Digital - MiArgentina | https://recibo-api-recibo-api-backend-qaext.arca.gob.ar/api |
| Ver | repro_ii_ws | Servicio web para la administración de solicitudes REPRO II | https://webserviceshomoext.afip.gob.ar/wsreproii/reproii.asmx |
| Ver | rsi_ws_perfil_configuracion | Servicio de configuración de parámetros e instrumentos de RSI. | https://setiwebhomo.afip.gob.ar/ws/Configuracion |
| Ver | rsi_ws_perfil_gestion | Servicio de gestión de tareas de RSI. | https://setiwebhomo.afip.gob.ar/ws/GestionTareas |
| Ver | rsiws | Servicio de configuración de parámetros e instrumentos de RSI. | https://setiwebhomo.afip.gob.ar/ws/configuracion |
| Ver | seah-ws | WS Seah | https://webserviceshomoext.afip.gob.ar/seah-ws/servicios.asmx |
| Ver | servicioindira | Intercambio de Informacion de los Registros Aduaneros | https://testdia.afip.gob.ar/DIA/WS/ServicioIndira/ServicioIndira.asmx?wsdl |
| Ver | serviciomicchile | Recepcion de Documentos Mic/Dta de Chile | https://testdia.afip.gob.ar/dia/ws/ServicioMicChile/ServicioMicChile.asmx |
| Ver | serviciosintia | Envio de Doc. MIC-DTA y seguimiento a traves de eventos | https://testdia.afip.gob.ar/dia/serviciosintia/serviciosintia.asmx |
| Ver | serviciosintia2 | Registracion de los Micdta, Eventos y Novedades provenientes del Mercosur | https://wsaduhomoext.afip.gob.ar/DIAV2/serviciosintia2/serviciosintia2.asmx |
| Ver | seti-edp-api | seti-edp-api | https://seti-edp-api-qaext.afip.gob.ar/ |
| Ver | setipagob2b_createvep | Creacion de VEPs para entidades externas | https://awshomo.afip.gov.ar/setiws/services/externalvepreceptor |
| Ver | seti-setipago-api | seti-setipago-api | https://seti-setipago-api-qaext.afip.gob.ar/ |
| Ver | siam-ccma-ws-arba | Webservice con deudas de CCMA para organismos externos - ARBA | https://webserviceshomoext.afip.gob.ar/deuda_ws/DeudaWS.asmx |
| Ver | siam-ccma-ws-deudas | Webservice con deudas de CCMA para organismos externos | https://webserviceshomoext.afip.gob.ar/deuda_ws/DeudaWS.asmx |
| Ver | siam-sicam-ws-anses | Webservice con deudas de SICAM para organismos externos | https://webserviceshomoext.afip.gob.ar/sicam_ws/PreSicam.asmx |
| Ver | simublanq_ws | Servicio web para la simulación de Régimen de regularización de activos. | https://webserviceshomoext.afip.gob.ar/wssimublanq/simublanq.asmx |
| Ver | simureibp_ws | Servicio web para la simulación de Régimen Especial del Ingreso del Impuesto sobre los Bienes Personales. | https://webserviceshomoext.afip.gob.ar/wssimureibp/simuREIBP.asmx |
| Ver | sire-external-api | Servicio para importar lotes de Sire (F2005) | https://sire-external-api-qaext.afip.gob.ar/sire-external/ |
| Ver | sire-ws | sire-ws | https://ws-aplicativos-reca.homo.afip.gob.ar/sire/ws/v1/c2005/2005 |
| Ver | soj-coelsa-ws | Servicio de intercambio de información AFIP-COELSA | https://soj-coelsa-ws-qaext.afip.gob.ar/ |
| Ver | sr-mi-argentina-rest | API REST que permite obtener Constancia de Inscripción desde la app MiArgentina | https://sr-mi-argentina-rest-qaext.afip.gob.ar/api |
| Ver | sr-rns-ws | RNS servicio de consulta de trámites pendientes | https://awshomo.afip.gov.ar/sr-rns/ws |
| Ver | sud_contrataciones | WEB SERVICE - PROVEEDORES DEL ESTADO | https://sud-ws.cloudhomo.afip.gob.ar/ws/sud_contrataciones |
| Ver | sud_restricciones | WS - para Entidades Financieras de Deudores Previsionales | https://sud-ws.cloudhomo.afip.gob.ar/sud_restricciones |
| Ver | trabajo_f931 | Consulta de F931 | https://testdia.afip.gob.ar/diirss/trabajoF931/F931.asmx |
| Ver | veconsumerws | Servicio para consultar y leer Comunicaciones publicadas en Ventanilla Electrónica | https://stable-middleware-tecno-ext.afip.gob.ar/ve-ws/services/veconsumer |
| Ver | vepublisher-mteyss | Servicio para Publicar Mensajes en Ventanilla Electrónica | https://stable-middleware-tecno-ext.afip.gob.ar/ve-ws/services/vepublisher-ext/ve-ws-ext/services/vepublisher-ext |
| Ver | wbajTabATATran | Transmisión Padrón de e ATAs y Transportistas | https://testdia.afip.gob.ar/Net/Gen/GenWs/wbajTabATATran/wbajTabATATran.asmx |
| Ver | wBajTabRef | Transmision de Tablas de Referencia | https://testdia.afip.gob.ar/dia/wbajTabRef/wbajTabRef.asmx |
| Ver | wccpacrom | Intercambio de Datos para Control CCPAC / CCROM | https://testdia.afip.gob.ar/Dia/ws/wCcPacRom/wCcPacRom.asmx?wsdl |
| Ver | wcerdesaran | Certificados de Desgravacion Arancelaria | https://testdia.afip.gob.ar/Dia/ws/WCerDesAran |
| Ver | wconsbienesregistrables | WS BIENES REGISTRABLES | https://wsaduhomoext.afip.gob.ar/diav2/wconsbienesregistrables/wconsbienesregistrables.asmx |
| Ver | wconscomunicacionembarque | Consultar Comunicaciones de Embarque | https://wsaduhomoext.afip.gob.ar/diav2/wconscomunicacionembarque/wconscomunicacionembarque.asmx |
| Ver | wconscourierselectividad | Web Service de Consulta de envios con selectividad para Couriers | https://wsaduhomoext.afip.gob.ar/DIAV2/wconscourierselectividad/wconscourierselectividad.asmx |
| Ver | wconscuit | WS - Consulta Cuit | https://wsaduhomoext.afip.gob.ar/diav2/wconscuit/wconscuit.asmx |
| Ver | wconscuit_dia | WS - Consulta Cuit - DIA | https://wsaduhomoext.afip.gob.ar/diav2/wconscuit_dia/wconscuit.asmx |
| Ver | wconsdeclaracion | Ws Consulta Declaracion | https://wsaduhomoext.afip.gob.ar/diav2/wconsdeclaracion/wconsdeclaracion.asmx |
| Ver | wconsdeclaracion_dia | Ws Consulta Declaracion -DIA | https://wsaduhomoext.afip.gob.ar/diav2/wconsdeclaracion_dia/wconsdeclaracion.asmx |
| Ver | wconsdepfiel | Consulta Depositario Fiel PSAD | https://testdia.afip.gob.ar/dia/ws/wConsDepFiel/wConsDepFiel.asmx |
| Ver | wconsdepositariofiel | WS Consulta Depositario Fiel | https://wsaduhomoext.afip.gob.ar/diav2/wconsdepositariofiel/wconsdepositariofiel.asmx |
| Ver | wconsdjai | Consulta de DJAI para Ministerio de Economía | https://testdia.afip.gob.ar/Dia/Ws/ w ConsDJA I/wConsDJAI.asmx |
| Ver | wconsdocrequeridos | Ws Arancel - Recortado | https://wsaduhomoext.afip.gob.ar/diav2/wconsdocrequeridos/wconsdocrequeridos.asmx |
| Ver | wconsdocrequeridos_dia | Ws Arancel - Recortado - DIA | https://wsaduhomoext.afip.gob.ar/diav2/wconsdocrequeridos_dia/wconsdocrequeridos.asmx |
| Ver | wconsglobalentry | Global Entry-Infractores | https://testdia.afip.gob.ar/Dia/Ws/wconsglobalentry/wconsglobalentry.asmx |
| Ver | wconsparam | Ws Consulta parametros | https://wsaduhomoext.afip.gob.ar/wconsparam/wconsparam.asmx |
| Ver | wconsparam_dia | Ws Consulta parametros - DIA | https://wsaduhomoext.afip.gob.ar/wconsparam_dia/wconsparam.asmx |
| Ver | wconsrecaudacion | Ws Consulta Recaudacion | https://wsaduhomoext.afip.gob.ar/diav2/wconsrecaudacion/wconsrecaudacion.asmx |
| Ver | wconsrecaudacion_dia | Ws Consulta Recaudacion - DIA | https://wsaduhomoext.afip.gob.ar/diav2/wconsrecaudacion_dia/wconsrecaudacion.asmx |
| Ver | wconssintia | Consulta de Mic-DTA | https://testdia.afip.gob.ar/Dia/Ws/WConsSintia/WConsSINTIA.asmx |
| Ver | wdepCerco | Coraza Electrónica de Seguridad (CES) | https://testdia.afip.gob.ar/DIA/WS/wdepCerco/wdepCerco.asmx |
| Ver | wdepMovimientos | Movimientos de Ingreso/Egreso para Terminales/Deposistarios | https://testdia.afip.gob.ar/Net/Gen/GenWs/wdepMovimientos/wdepMovimientos.asmx |
| Ver | wdeppesobalanza | Ingreso de Peso de Balanza MIC-DTA | https://testdia.afip.gob.ar/dia/ws/wdepPesoBalanza/wdepPesoBalanza.asmx |
| Ver | wdepPesoBalanza | Ingreso de Peso de Balanza | https://testdia.afip.gob.ar/Net/Gen/GenWs/wdepPesoBalanza/wdepPesoBalanza.asmx |
| Ver | wdiautides | Movimiento de contenedores con DES | https://testdia.afip.gob.ar/DIA/WS/WdiaUtiDes/WdiaUtiDes.asmx?WSDL |
| Ver | WdiaUtiDes | Movimiento de contenedores con DES | https://testdia.afip.gob.ar/DIA/WS/WdiaUtiDes/WdiaUtiDes.asmx?WSDL |
| Ver | wDigDepFiel | Digitalizacion de Depositario Fiel | https://testdia.afip.gob.ar/DIA/WS/wDigDepFiel/wDigDepFiel.asmx |
| Ver | wEnysa | Recepcion de Eventos de Entrada y Salida de Vehiculos | https://testdia.afip.gob.ar/DIA/WS/wEnysa/wEnysa.asmx |
| Ver | wgesacreditorigen | Información del trámite de acreditación de origen | https://wsaduhomoext.afip.gob.ar/diav2/wgesacreditorigen/wgesacreditorigen.asmx |
| Ver | wgesaprobaciondj | Neumáticos Aprobación SIRA | https://wsaduhomoext.afip.gob.ar/diav2/wgesaprobaciondj/wgesaprobaciondj.asmx |
| Ver | wgesaprobitem | Aprobación / Denegatoria de Declaración por Ítem | https://testdia.afip.gob.ar/dia/ws/wgesAprobItem/wgesAprobItem.asmx?WSDL |
| Ver | wgesaralistas | WS ARANCEL - Gestión de Listas | https://wsaduhomoext.afip.gob.ar/diav2/wgesaralistas/wgesaralistas.asmx |
| Ver | wgesautgirodivisas | WS wgesautgirodivisas | https://wsaduhomoext.afip.gob.ar/diav2/wgesautgirodivisas/wgesautgirodivisas.asmx |
| Ver | wgescertderivado | Ws wgescertderivados | https://wsaduhomoext.afip.gob.ar/DIAV2/wgescertderivado/wgescertderivado.asmx |
| Ver | wgescomunicacionembarque | Web Services Comunicación de Embarque | https://wsaduhomoext.afip.gob.ar/diav2/wgescomunicacionembarque/wgescomunicacionembarque.asmx |
| Ver | wgescontrolsanitario | Control Sanitario para Embalajes de Madera | https://testdia.afip.gob.ar/dia/ws/wgescontrolsanitario/wgescontrolsanitario.asmx |
| Ver | wgescouparticulares | WS de Courier | https://wsaduhomoext.afip.gob.ar/diav2/wgescouparticulares/wgescouparticulares.asmx |
| Ver | wgesdeclaracion | Ws Gestion Declaracion | https://wsaduhomoext.afip.gob.ar/diav2/wgesdeclaracion/wgesdeclaracion.asmx |
| Ver | wgesdeclaracion_dia | Ws Gestion Declaracion - DIA | https://wsaduhomoext.afip.gob.ar/diav2/wgesdeclaracion_dia/wgesdeclaracion.asmx |
| Ver | wgesdescargamaritima | WS - Comunicación de descarga via marítima | https://wsaduhomoext.afip.gob.ar/diav2/wgesdescargamaritima/wgesdescargamaritima.asmx |
| Ver | wgesdespa | Consulta y Novedades de Destinaciones Detalladas | https://testdia.afip.gob.ar/DIA/WS/wgesdespa/wgesdespa.asmx |
| Ver | wgesdetallada | WS - Transferencia de la Declaracion Detallada | https://testdia.afip.gob.ar/Dia/ws/wgestabref/wgesdetallada.asmx |
| Ver | wgesenviosaaetnc | Pequenos envios AAE al TNC | https://wsaduhomoext.afip.gob.ar/diav2/wgesenviosaaetnc/wgesenviosaaetnc.asmx |
| Ver | wgesenysa | WS ENYSA - Nuevo | https://wsaduhomoext.afip.gob.ar/diav2/wgesenysa |
| Ver | wgesepi | WS GESTION EPI | https://wsaduhomoext.afip.gob.ar/diav2/wgesepi/wgesepi.asmx |
| Ver | wgesepi_dia | ws wgesepi_dia | https://wsaduhomoext.afip.gob.ar/diav2/wGESEPI_dia/wGESEPI.asmx |
| Ver | wgesescaneres | Intercambio de información con los escáneres de aduana | https://testdia.afip.gob.ar/dia/ws/wgesescaneres/wgesescaneres.asmx |
| Ver | wgesexportasimple | WS wgesexportasimple | https://wsaduhomoext.afip.gob.ar/diav2/wgesexportasimple/wgesexportasimple.asmx |
| Ver | wgesinfantiataxffm | (Flight Manifest Message) | https://testdia.afip.gob.ar/dia/ws/wgesinfantiataxffm/wgesinfantiataxffm.asmx |
| Ver | wgesinfantiataxfhl | (House Manifest Message) | https://testdia.afip.gob.ar/dia/ws/wgesinfantiataxfhl/wgesinfantiataxfhl.asmx |
| Ver | wgesinfantiataxfwb | Waybill Message | https://testdia.afip.gob.ar/dia/ws/wgesinfantiataxfwb/wgesinfantiataxfwb.asmx |
| Ver | wgesinfantiataxfzb | House Waybill Message HOMO | https://testdia.afip.gob.ar/dia/ws/wgesinfantiataxfzb/wgesinfantiataxfzb.asmx |
| Ver | wgesinformacionanticipada | WS INFORMACION ANTICIPADA MARITIMA | https://wsaduhomoext.afip.gob.ar/diav2/wgesinformacionanticipada/wgesinformacionanticipada.asmx |
| Ver | wgesinformacionanticipada_dia | WS INFORMACION ANTICIPADA MARITIMA (DIA) | https://wsaduhomoext.afip.gob.ar/DIAV2/wgesinformacionanticipada_dia/wgesinformacionanticipada.asmx |
| Ver | wgesingresosbrutos | WS Ingresos Bruos Comision Arbitral | https://wsaduhomoext.afip.gob.ar/diav2/wgesingresosbrutos/wgesingresosbrutos.asmx |
| Ver | wgesinv | Consulta y Desbloqueo de Despachos INV | https://testdia.afip.gob.ar/Dia/ws/WGesINV |
| Ver | wgeslpco | WS LPCO | https://wsaduhomoext.afip.gob.ar/diav2/wgeslpco/wgeslpco.asmx |
| Ver | wgesmigracionespasajeros | WS MIGRACIONES PASAJEROS | https://wsaduhomoext.afip.gob.ar/diav2/wgesmigracionespasajeros/wgesmigracionespasajeros.asmx |
| Ver | wgespagosliq_dia | Ws Gestion Pagos - DIA | https://wsaduhomoext.afip.gob.ar/diav2/wgespagosliq_dia/wgespagosliq.asmx |
| Ver | wgespaut | Gestión Padrón de Transportistas | https://testdia.afip.gob.ar/Dia/ws/wGesPAUT/wGesPAUT.asmx?wsdl |
| Ver | wgesprecintosdepfis | Cerrojo electronico de Depositos Fiscales | https://testdia.afip.gob.ar/dia/ws/wgesprecintosdepfis/wgesprecintosdepfis.asmx |
| Ver | wgesregsintia2 | wgesregsintia2 | https://wsaduhomoext.afip.gob.ar/DIAV2/wgesregsintia2/wgesregsintia2.asmx |
| Ver | wgessobredigital | WS wgessobredigital | https://wsaduhomoext.afip.gob.ar/diav2/wgessobredigital/wgessobredigital.asmx |
| Ver | wgesstockdepositosfiscales | Stock depósitos Fiscales | https://wsaduhomoext.afip.gob.ar/diav2/wgesstockdepositosfiscales/wgesstockdepositosfiscales.asmx |
| Ver | wGesTabRef | Consulta de Tablas de Referencia | https://testdia.afip.gob.ar/Dia/ws/wgestabref/wgestabref.asmx |
| Ver | wgestiendaslibres | WS Gestión tiendas libres de impuestos | https://wsaduhomoext.afip.gob.ar/diav2/wgestiendaslibres/wgestiendaslibres.asmx |
| Ver | wgestimbrefiscalelectronico | Registro y actualización del Timbrado Fiscal Electrónico para destinaciones con productos de electrónica que cuenten con código IMEI. | https://wsaduhomoext.afip.gob.ar/diav2/wgestimbrefiscalelectronico/wgestimbrefiscalelectronico.asmx |
| Ver | wgesvuelosciviles | WS - Vuelos Civiles | https://wsaduhomoext.afip.gob.ar/DIAV2/wgesvuelosciviles/wgesvuelosciviles.asmx |
| Ver | wgeszonafrancaventaminorista | Zona franca venta minorista | https://wsaduhomoext.afip.gob.ar/diav2/wgeszonafrancaventaminorista/wgeszonafrancaventaminorista.asmx |
| Ver | whelperdeclaracion | Ws Helper Declaracion | https://wsaduhomoext.afip.gob.ar/diav2/whelperdeclaracion/whelperdeclaracion.asmx |
| Ver | whelperdeclaracion_dia | Ws Helper Declaracion - DIA | https://wsaduhomoext.afip.gob.ar/diav2/whelperdeclaracion_dia/whelperdeclaracion.asmx |
| Ver | WLami | Consulta Datos Licencias Previas para la Secretaria de Minería | https://testdia.afip.gob.ar/Dia/ws/WLami |
| Ver | worgafectaciongarantia | Webservice para gestión de afectaciones de garantías | https://wsaduhomoext.afip.gob.ar/diav2/worgafectaciongarantia/worgafectaciongarantia.asmx |
| Ver | ws_aerolineas_b | WS Beneficios Aerolíneas Argentinas | https://admws.cloudhomo.afip.gob.ar/aerolineas-ws/beneficios |
| Ver | ws_ddjj_ss | Consultas de DDJJ de Seguridad Social - Nivel 01 | https://testdia.afip.gob.ar/diirss/wsddjj/ws01.asmx?wsdl |
| Ver | ws_pdf_librosueldos | Servicio diseñado para el envio de los pdf de libro de sueldos a otras entidades gubernamentales | https://webserviceshomoext.afip.gob.ar/misimplificacion-ws-ls/WsPDFLibroDeSueldos.asmx |
| Ver | ws_sr_constancia_inscripcion | Web service de Consulta de la Constancia de Inscripción de Padrón | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5 |
| Ver | ws_sr_padron_a10 | Servicio de consulta Padrón a10 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA10 |
| Ver | ws_sr_padron_a100 | Servicio Consulta de parámetros de padrón | https://awshomo.afip.gov.ar/sr-parametros/webservices/parameterServiceA100 |
| Ver | ws_sr_padron_a13 | WS de consulta padron A13 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13 |
| Ver | ws_sr_padron_a20 | Servicio Consulta y actualización Padron A20 | https://awshomo.afip.gov.ar/sr-padron/webservices/documentoDigitalServiceA20 |
| Ver | ws_sr_padron_a4 | Servicio Consulta Padron A4 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServicioA4 |
| Ver | ws_sr_padron_a5 | WS de Consulta Padron A5 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5 |
| Ver | ws_sr_padron_a6 | Servicio Consulta y actualización Padron A6 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServicioA6 |
| Ver | ws_sr_padron_a7 | Servicio Consulta y actualización Padron A7 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA7 |
| Ver | ws_sr_padron_a9 | WS de consulta Padrón A9 | https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA9 |
| Ver | wsagr | Archivo de Proveedores - Reproweb | https://wswhomo.afip.gov.ar/wsagr/wsagr.asmx |
| Ver | wsapoc | WS de Consulta Base APOC | https://eapoc-ws-qaext.afip.gob.ar/Service.asmx |
| Ver | wsbfe | Bonos Fiscales Electronicos - BFE | https://wswhomo.afip.gov.ar/wsbfe/service.asmx |
| Ver | wscdc | Constatación de Comprobantes - Web Service | https://wswhomo.afip.gov.ar/wscdc/service.asmx |
| Ver | wscec | CONSULTAS DE COMPROBANTES SUJETOS A LA LEY DE ECONOMÍA DEL CONOCIMIENTO | https://fwshomo.afip.gov.ar/wscec/CECService |
| Ver | ws-check-ar | Determina si una persona física es administrador de relaciones de la persona jurídica | https://wsaahomo.afip.gov.ar/ws-check-ar/CheckArService/CheckBean |
| Ver | ws-check-subar | Determina si una persona física es subadministrador de relaciones de la persona jurídica | https://wsaahomo.afip.gov.ar/ws-check-subar/CheckSubArService/CheckBean |
| Ver | wscomunicacionembarque | Comunicación de Embarque | https://wsaduhomoext.afip.gob.ar/DIAV2/wgescomunicacionembarque/wgescomunicacionembarque.asmx |
| Ver | ws-consulta-autorizaciones-cf | Consulta autorizaciones | https://wsaahomo.afip.gov.ar/ws-consulta-autorizaciones-cf/ConsultaAutorizacionesBean |
| Ver | wscpe | Web Service Carta de porte Electrónica | https://cpea-ws-qaext.afip.gob.ar/wscpe/services/soap |
| Ver | wsct | Web Service Comprobantes T | https://fwshomo.afip.gov.ar/wsct/CTService |
| Ver | wscta | Certificados DNRPA | https://fwshomo.afip.gov.ar/wscta/services/CertificadoDNRPAService |
| Ver | wsdeuda_deuda_seg_soc | Servicio de Consulta de Deuda Seguridad Social. | https://awshomo.afip.gov.ar/cuentacorriente-ws/DeudaWs |
| Ver | wsdtve | Web Service DTVe | https://fwshomo.afip.gov.ar/wsdtve/services |
| Ver | wseptr | Web Service Evaluador ANSES | https://fwshomo.afip.gov.ar/wseptr/EPTRService |
| Ver | wsexposimple | Webservice Exportación Simplificada | https://fwshomo.afip.gov.ar/wsexposimple/ExpoSimpleService |
| Ver | wsfe | Facturacion Electronica | https://wswhomo.afip.gov.ar/wsfe/service.asmx |
| Ver | wsfecred | Registro de Facturas de Crédito Electrónica MiPyMEs | https://fwshomo.afip.gov.ar/wsfecred/FECredService |
| Ver | wsfecredagente | WS Agente de Depósito Colectivo o similares | https://fwshomo.afip.gov.ar/wsfecredadc/FECredADCService |
| Ver | wsfecredsca | WS SISTEMA DE CIRCULACION ABIERTA BCRA | https://fwshomo.afip.gov.ar/wsfecredsca/FECredSCAService |
| Ver | wsfex | Factura electronica de exportacion- FEX | https://webserviceshomoext.afip.gob.ar/Fiscalizacion/wsfex/Service.asmx |
| Ver | wsgrp | Web Service SOAP para la gestión de tickets de proveedores | https://wswhomo.afip.gov.ar/wsgrp/service.asmx |
| Ver | wsgs1 | Servicios de GS1 | https://fwshomo.afip.gov.ar/wsgs1/PadronProductos |
| Ver | wsicdb | Web Service Beneficios Fiscales en el Impuesto sobre los Créditos y Débitos en Cuentas Bancarias - Agentes de Liquidación (Bancos) | https://fwshomo.afip.gov.ar/wsicdb/IcdbService |
| Ver | wsjaza | Web Service JAZA | https://fwshomo.afip.gov.ar/wsjaza/JAZAService |
| Ver | wslca | Web Service Liquidación Caña de Azúcar | https://fwshomo.afip.gov.ar/wslca/services/soap |
| Ver | wslibrosueldos | Webservice Libro De Sueldos Digital Inforamción a organismos | https://webserviceshomoext.afip.gob.ar/tramites_con_clave_fiscal/WsLibrosueldos/wslibrosueldos.asmx |
| Ver | wslpg | Web Service de Liquidación Primaria de Granos | https://fwshomo.afip.gov.ar/wslpg/LpgService |
| Ver | wslsp | Web Service de Liquidación Sector Pecuario | https://fwshomo.afip.gov.ar/wslsp/LspService |
| Ver | wsltv | Web Service de Tabaco - Liquidacion electrónica | https://fwshomo.afip.gov.ar/wsltv/LtvService |
| Ver | wslum | Web Service de Lecheria - Liquidación electrónica | https://fwshomo.afip.gov.ar/wslum/LumService |
| Ver | wsminprodf931 | Web service para uso de ministerio de producción (Textiles, Detracción Especial) | https://webserviceshomoext.afip.gob.ar/MinProdF931/MinProdF931.asmx |
| Ver | wsmintransp | webservice para uso del ministerio de transporte (consulta relaciones laborales) | https://webserviceshomoext.afip.gob.ar/wsMinTransp/MinTransp.asmx |
| Ver | wsmtxca | Factura Electrónica con Detalle - MTXCA | https://fwshomo.afip.gov.ar/wsmtxca/services/MTXCAService |
| Ver | wsnaperr | Automatizacion Res. Revocacion A.P.E | https://testdia.afip.gob.ar/wsnaperr/service.asmx |
| Ver | wsn-rest | wsn-rest | https://wsaa.rest.afip.gob.ar/wsn-rest/api/service/validate |
| Ver | wspagodte | Consulta de pagos para DTE | https://fwshomo.afip.gov.ar/wspagodte/services/PagoDTEService |
| Ver | wspcp | Padron Cliente Proveedor | https://fwshomo.afip.gov.ar/wsfeca/services/FECAService |
| Ver | wspesquero | Web Service Guia de Pesca | https://fwshomo.afip.gov.ar/wspesquero/service |
| Ver | wspresupuesto | WS - Kit Presupuesto | https://testdia.afip.gob.ar/dia/ws/wspresupuesto/wspresupuesto.asmx |
| Ver | wspublicacionretra | Publicacion de requerimientos en Retra | https://webserviceshomoext.afip.gob.ar/WsPublicacionRetra/Relevamientos.asmx |
| Ver | wsregapi | Servicio Consulta Tarjetas REGAPI 1 | https://wsregapi-homoext.afip.gob.ar/regapi/wsregapi |
| Ver | wsrellabext | Web Services de Relaciones Laborales | https://testdia.afip.gob.ar/diirss/wsrelacioneslaborales/rellab.asmx |
| Ver | wsremarba | Web Service Intercambio Información Remito | https://wsaduhomoext.afip.gob.ar/Fiscalizacion/wsremarba/Remitos.asmx |
| Ver | wsremazucar | Web Service Remito Azucar | https://fwshomo.afip.gov.ar/wsremazucar/RemAzucarService |
| Ver | wsremcarne | Web Service Remito Carne | https://fwshomo.afip.gov.ar/wsremcarne/RemCarneService |
| Ver | wsremharina | Web Service Remito Harina | https://fwshomo.afip.gov.ar/wsremharina/RemHarinaService |
| Ver | wsrgiva | Regimen Percepcion IVA | https://fwshomo.afip.gov.ar/wsrgiva/services/RegimenPercepcionIVAService?wsdl |
| Ver | wsseg | Operacion de Seguros de Caucion | https://wswhomo.afip.gov.ar/wsseg/service.asmx |
| Ver | wssicamsica | Consultas sobre el calculo de SICAM | https://testdia.afip.gob.ar/tramites_con_clave_fiscal/SicamSicaWS/sicamsicaws.asmx?wsdl |
| Ver | wssisaorg | Web Service SISA ORG | https://fwshomo.afip.gov.ar/wssisaorg/services |
| Ver | wssv3 | Web Service SOAP para el seguimiento de vehículos | https://wswhomo.afip.gov.ar/wssv3/service.asmx |
| Ver | wstabaco | Web Service de Tabaco – Régimen Tabacalero | https://fwshomo.afip.gov.ar/wstabaco/TabacoService |
| Ver | ws-test-wsauth | ws-test-wsauth | https://wsauthhomo-ext.afip.gob.ar/ws-test-wsauth |
| Ver | wsturiva | Reintegro de IVA a turistas extranjeros | https://fwshomo.afip.gov.ar/wsturiva/Turiva?wsdl |
| Ver | wutiDestinaciones | Transmision de Destinaciones para Terminales/Depositarios | https://testdia.afip.gob.ar/Dia/Ws/wutiDestinaciones/wutiDestinaciones.asmx |
| Ver | wutigopdeclaraciones | Transmision de Declaraciones a Grandes Operadores | https://testdia.afip.gob.ar/dia/Ws/wutigopdeclaraciones/wutigopdeclaraciones.asmx |
