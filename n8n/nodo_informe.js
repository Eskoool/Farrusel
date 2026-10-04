// Nodo Code de n8n · "Construir informe" (modo: Run Once for All Items)
// Lee uso_evento y evento_kardex de Supabase (políticas de lectura para la clave pública),
// construye el resumen y el informe HTML interactivo, y lo deja como adjunto binario.
// El marcador /*__TEMPLATE__*/ lo sustituye n8n/build_workflow.py con n8n/informe_template.html.
const TEMPLATE = /*__TEMPLATE__*/'';

const cfg = $input.first().json;
const hoy = new Date();

// Guarda: el disparo programado solo actúa en 2026. La prueba manual se salta la guarda.
if (cfg.modo !== 'prueba' && hoy.getUTCFullYear() !== 2026) {
  return [];
}

const traer = async (tabla, columnas) => {
  const filas = [];
  const paso = 1000; // PostgREST corta a 1000 filas por petición
  for (let pagina = 0; pagina < 200; pagina++) {
    const desde = pagina * paso;
    const lote = await this.helpers.httpRequest({
      method: 'GET',
      url: `${cfg.supabaseUrl}/rest/v1/${tabla}?select=${columnas}&order=id.asc`,
      headers: {
        apikey: cfg.anonKey,
        Authorization: `Bearer ${cfg.anonKey}`,
        'Range-Unit': 'items',
        Range: `${desde}-${desde + paso - 1}`,
      },
      json: true,
    });
    filas.push(...lote);
    if (lote.length < paso) break;
  }
  return filas;
};

const uso = await traer('uso_evento', 'pantalla,accion,creado_en');
const eventos = await traer('evento_kardex', 'tipo,creado_en,procesado_en,resultado');

const n = (arr, f) => arr.filter(f).length;
const resumen = {
  cortes: n(eventos, e => e.tipo === 'corte_cargado'),
  gestion: n(uso, u => u.pantalla === 'gestion' && u.accion === 'abrir'),
  subida: n(uso, u => u.pantalla === 'subida' && u.accion === 'abrir'),
  aceptadas: n(eventos, e => e.tipo === 'propuesta_aceptada'),
  rechazadas: n(eventos, e => e.tipo === 'propuesta_rechazada'),
  aplicadas: n(eventos, e => e.tipo === 'propuesta_aplicada'),
  pendientes: n(eventos, e => !e.procesado_en),
  totalEventos: eventos.length,
};

const datos = { uso, eventos, generado: hoy.toISOString().slice(0, 10) };
const json = JSON.stringify(datos).replace(/</g, '\\u003c');
const html = TEMPLATE.replace('/*__DATA__*/null', () => json);

const cuerpo = `<h2>Farrusel · faltan 7 días para los resultados (31-12-2026)</h2>
<p>Resumen de uso (solo agregados; el detalle interactivo va en el adjunto):</p>
<ul>
<li>Cortes cargados: <b>${resumen.cortes}</b> (objetivo: al menos 1 al mes)</li>
<li>Consultas de Gestión Kardex: <b>${resumen.gestion}</b> (objetivo: al menos 4 al mes) · aperturas de Subida: <b>${resumen.subida}</b></li>
<li>Propuestas aceptadas: <b>${resumen.aceptadas}</b> · rechazadas: <b>${resumen.rechazadas}</b> · aplicadas: <b>${resumen.aplicadas}</b></li>
<li>Eventos pendientes de procesar: <b>${resumen.pendientes}</b> de ${resumen.totalEventos}
 (sin consumidor externo hasta la v1.1 con Frello, el 95 % de la métrica 2 aún no es medible)</li>
</ul>
<p><b>Abre el adjunto <i>informe-farrusel.html</i> en el navegador</b> (doble clic): tiene filtros, orden y barras por mes.</p>
<p style="color:#666">Mensaje automático de n8n. Métricas definidas en el PRD §2.${cfg.modo === 'prueba' ? ' <b>ENVÍO DE PRUEBA.</b>' : ''}</p>`;

const binario = await this.helpers.prepareBinaryData(
  Buffer.from(html, 'utf8'), 'informe-farrusel.html', 'text/html');

return [{
  json: {
    destino: cfg.destino,
    asunto: `${cfg.modo === 'prueba' ? '[PRUEBA] ' : ''}Farrusel · faltan 7 días para los resultados`,
    cuerpo,
    resumen,
  },
  binary: { informe: binario },
}];
