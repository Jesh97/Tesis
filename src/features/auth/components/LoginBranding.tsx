import { AnchorIcon, ShieldCheckIcon } from '../../../components/icons'

export function LoginBranding() {
  return (
    <div className="relative flex flex-col justify-between overflow-hidden bg-slate-900 p-10 text-white sm:p-14">
      <div
        className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1505118380757-91f5f5632de0?auto=format&fit=crop&w=1200&q=80')] bg-cover bg-center opacity-40"
        aria-hidden="true"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-900/70 to-slate-950/90" />

      <div className="relative z-10 flex items-center gap-2 text-sm tracking-wide">
        <AnchorIcon className="h-5 w-5" />
        <div className="leading-tight">
          <p className="font-semibold uppercase">Ministerio de la Producción</p>
          <p className="text-slate-300">Gobierno del Perú</p>
        </div>
      </div>

      <div className="relative z-10 max-w-md">
        <h1 className="text-3xl leading-tight font-semibold sm:text-4xl">
          Sistema de Detección de Pesca Ilegal
        </h1>
        <p className="mt-4 text-sm leading-relaxed text-slate-300">
          Plataforma institucional para el monitoreo, control y vigilancia del
          espacio marítimo nacional (Mar de Grau). Acceso restringido para
          personal autorizado.
        </p>
      </div>

      <div className="relative z-10 flex items-center gap-2 text-xs text-slate-300">
        <ShieldCheckIcon className="h-4 w-4" />
        <span className="tracking-wide uppercase">Conexión segura cifrada</span>
      </div>
    </div>
  )
}
