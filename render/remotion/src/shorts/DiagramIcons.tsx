// The fixed icon set a systems short's nodes draw from (diagram/spec.py ICONS): line icons on a 64-unit grid, drawn in
// the node's tone.

const S = {fill: 'none', stroke: 'currentColor', strokeWidth: 4.5, strokeLinecap: 'round', strokeLinejoin: 'round'} as const;
const F = {fill: 'currentColor', stroke: 'none'} as const;

const ICONS: Record<string, React.ReactNode> = {
  client: (
    <>
      <rect x={7} y={10} width={50} height={34} rx={4} {...S} />
      <path d="M32 44v9M20 55h24" {...S} />
    </>
  ),
  users: (
    <>
      <circle cx={24} cy={22} r={8} {...S} />
      <path d="M8 52c0-10 7-16 16-16s16 6 16 16" {...S} />
      <circle cx={44} cy={20} r={6} {...S} />
      <path d="M42 34c8 0 14 5 14 14" {...S} />
    </>
  ),
  browser: (
    <>
      <rect x={6} y={10} width={52} height={44} rx={5} {...S} />
      <path d="M6 22h52" {...S} />
      <circle cx={13} cy={16} r={1.8} {...F} />
      <circle cx={19} cy={16} r={1.8} {...F} />
      <circle cx={25} cy={16} r={1.8} {...F} />
    </>
  ),
  phone: (
    <>
      <rect x={18} y={6} width={28} height={52} rx={6} {...S} />
      <path d="M28 50h8" {...S} />
    </>
  ),
  dns: (
    <>
      <path d="M32 8v48" {...S} />
      <path d="M32 13h17l6 6-6 6H32z" {...S} />
      <path d="M32 30H15l-6 6 6 6h17z" {...S} />
    </>
  ),
  cdn: (
    <>
      <circle cx={32} cy={32} r={22} {...S} />
      <ellipse cx={32} cy={32} rx={9} ry={22} {...S} />
      <path d="M10 32h44" {...S} />
      <circle cx={17} cy={21} r={4} {...F} />
      <circle cx={47} cy={22} r={4} {...F} />
      <circle cx={31} cy={48} r={4} {...F} />
    </>
  ),
  region: <path d="M18 46h28a10 10 0 0 0 1-20 14 14 0 0 0-27-3 11.5 11.5 0 0 0-2 23z" {...S} />,
  api_gateway: (
    <>
      <path d="M9 54V26l23-14 23 14v28" {...S} />
      <path d="M24 54V38h16v16" {...S} />
    </>
  ),
  load_balancer: (
    <>
      <rect x={7} y={7} width={50} height={50} rx={11} {...S} />
      <path d="M16 32h13M29 32l15-12M29 32h15M29 32l15 12" {...S} />
      <path d="M40 17l5 3-3 5M41 29l4 3-4 3M42 39l3 5-5 1" {...S} strokeWidth={3} />
    </>
  ),
  server: (
    <>
      <rect x={9} y={7} width={46} height={14} rx={3} {...S} />
      <rect x={9} y={25} width={46} height={14} rx={3} {...S} />
      <rect x={9} y={43} width={46} height={14} rx={3} {...S} />
      <circle cx={41} cy={14} r={2} {...F} />
      <circle cx={47} cy={14} r={2} {...F} />
      <circle cx={41} cy={32} r={2} {...F} />
      <circle cx={47} cy={32} r={2} {...F} />
      <circle cx={41} cy={50} r={2} {...F} />
      <circle cx={47} cy={50} r={2} {...F} />
    </>
  ),
  function: (
    <>
      <rect x={7} y={7} width={50} height={50} rx={11} {...S} />
      <path d="M21 17c6 0 8 4 10 10l7 20M27 47l8-17" {...S} />
    </>
  ),
  worker: (
    <>
      <circle cx={32} cy={32} r={11} {...S} />
      <path d="M32 8v8M32 48v8M8 32h8M48 32h8M15 15l6 6M43 43l6 6M15 49l6-6M43 21l6-6" {...S} />
    </>
  ),
  queue: (
    <>
      <rect x={5} y={22} width={11} height={20} rx={2} {...S} />
      <rect x={19} y={22} width={11} height={20} rx={2} {...S} />
      <rect x={33} y={22} width={11} height={20} rx={2} {...S} />
      <rect x={47} y={22} width={11} height={20} rx={2} {...F} />
    </>
  ),
  cache: (
    <>
      <rect x={7} y={7} width={50} height={50} rx={11} {...S} />
      <path d="M35 14L22 35h10l-3 15 13-21H32z" {...S} strokeWidth={3.5} />
    </>
  ),
  database: (
    <>
      <ellipse cx={32} cy={14} rx={20} ry={7} {...S} />
      <path d="M12 14v36c0 4 9 7 20 7s20-3 20-7V14" {...S} />
      <path d="M12 32c0 4 9 7 20 7s20-3 20-7" {...S} />
    </>
  ),
  replica: (
    <>
      <ellipse cx={22} cy={18} rx={13} ry={5} {...S} />
      <path d="M9 18v26c0 3 6 5 13 5s13-2 13-5V18" {...S} />
      <ellipse cx={42} cy={24} rx={13} ry={5} {...S} />
      <path d="M29 24v26c0 3 6 5 13 5s13-2 13-5V24" {...S} />
    </>
  ),
  storage: (
    <>
      <rect x={8} y={12} width={48} height={12} rx={3} {...S} />
      <path d="M12 24v28h40V24M26 33h12" {...S} />
    </>
  ),
  auth: (
    <>
      <rect x={14} y={28} width={36} height={28} rx={5} {...S} />
      <path d="M22 28v-8a10 10 0 0 1 20 0v8" {...S} />
      <circle cx={32} cy={41} r={3.5} {...F} />
    </>
  ),
};

export const Icon: React.FC<{name: string; size: number; color: string}> = ({name, size, color}) => (
  <svg width={size} height={size} viewBox="0 0 64 64" style={{color, overflow: 'visible'}}>
    {ICONS[name] ?? ICONS.server}
  </svg>
);
