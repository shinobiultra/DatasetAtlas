/** A small stroke-icon set. Icons are decorative; every control carries a text label or aria-label. */
type Props = { size?: number; className?: string }

function base(size: number, className?: string) {
  return {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const, className, 'aria-hidden': true, focusable: false,
  }
}

export const Search = ({ size = 15, className }: Props) => <svg {...base(size, className)}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
export const Grid = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="3" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" /><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" /><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" /></svg>
export const Rows = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="3" y="4.5" width="18" height="15" rx="2" /><path d="M3 9.5h18M3 14.5h18M9 4.5v15" /></svg>
export const MapIcon = ({ size = 15, className }: Props) => <svg {...base(size, className)}><circle cx="7" cy="8" r="1.6" /><circle cx="15.5" cy="6.5" r="1.6" /><circle cx="17.5" cy="14" r="1.6" /><circle cx="9" cy="16" r="1.6" /><circle cx="12.5" cy="11" r="1.6" /></svg>
export const Database = ({ size = 15, className }: Props) => <svg {...base(size, className)}><ellipse cx="12" cy="6" rx="8" ry="3" /><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>
export const Folder = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M3 7.5A1.5 1.5 0 0 1 4.5 6h4l2 2.5h7A1.5 1.5 0 0 1 19 10v7.5A1.5 1.5 0 0 1 17.5 19h-13A1.5 1.5 0 0 1 3 17.5z" /></svg>
export const Activity = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M3 12h4l3-7 4 14 3-7h4" /></svg>
export const Gear = ({ size = 15, className }: Props) => <svg {...base(size, className)}><circle cx="12" cy="12" r="3" /><path d="M19.4 14.5a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.3a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H3a2 2 0 0 1 0-4h.2a1.6 1.6 0 0 0 1.1-2.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 2.7-1.1V3a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 2.8 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.3a2 2 0 0 1 0 4h-.2a1.6 1.6 0 0 0-1.4 1z" /></svg>
export const Star = ({ size = 15, className, filled = false }: Props & { filled?: boolean }) => <svg {...base(size, className)} fill={filled ? 'currentColor' : 'none'}><path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z" /></svg>
export const Close = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M6 6l12 12M18 6 6 18" /></svg>
export const ChevronLeft = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="m14.5 5-7 7 7 7" /></svg>
export const ChevronRight = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="m9.5 5 7 7-7 7" /></svg>
export const ChevronDown = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="m5 9.5 7 7 7-7" /></svg>
export const Expand = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M9 3H3v6M15 21h6v-6M3 15v6h6M21 9V3h-6" /></svg>
export const Columns = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="3" y="4.5" width="18" height="15" rx="2" /><path d="M9.5 4.5v15M15 4.5v15" /></svg>
export const Filter = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M4 5.5h16l-6.2 7.3v5.4l-3.6 1.8v-7.2z" /></svg>
export const Sparkle = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M12 3.5 13.7 9l5.5 1.7-5.5 1.7L12 18l-1.7-5.6L4.8 10.7 10.3 9z" /></svg>
export const Chat = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M20 12a7.5 7.5 0 0 1-10.9 6.7L4 20l1.3-4.2A7.5 7.5 0 1 1 20 12z" /></svg>
export const Compare = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="3" y="5" width="7.5" height="14" rx="1.5" /><rect x="13.5" y="5" width="7.5" height="14" rx="1.5" /></svg>
export const Download = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M12 4v10m0 0 4-4m-4 4-4-4M4 18h16" /></svg>
export const Bookmark = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M6 4.5h12v16l-6-4-6 4z" /></svg>
export const Info = ({ size = 15, className }: Props) => <svg {...base(size, className)}><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5.5M12 7.8v.4" /></svg>
export const Warning = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M12 4.2 21 19H3z" /><path d="M12 10v4M12 16.6v.3" /></svg>
export const Image = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="3" y="4.5" width="18" height="15" rx="2" /><circle cx="8.5" cy="9.5" r="1.6" /><path d="m4 17 5-4.5 4 3.2 3-2.4 4 3.4" /></svg>
export const Layers = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="m12 3 9 5-9 5-9-5z" /><path d="m3.5 12.5 8.5 4.7 8.5-4.7" /></svg>
export const Play = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M7 4.7 19 12 7 19.3z" /></svg>
export const Menu = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
export const Plus = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M12 5v14M5 12h14" /></svg>
export const Copy = ({ size = 15, className }: Props) => <svg {...base(size, className)}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5.5A1.5 1.5 0 0 1 6.5 4H15" /></svg>
export const Reset = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M4 10a8 8 0 1 1 1.2 6" /><path d="M4 4.5V10h5.5" /></svg>
export const Text = ({ size = 15, className }: Props) => <svg {...base(size, className)}><path d="M5 6h14M5 11h14M5 16h9" /></svg>
