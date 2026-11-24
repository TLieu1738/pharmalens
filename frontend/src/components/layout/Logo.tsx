import { cn } from '@/lib/utils'

/** PharmaLens wordmark. `size` sets the rendered height; the image keeps its aspect ratio. */
export function Logo({ tagline = false, size = 'md' }: { tagline?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  return (
    <div>
      <img
        src="/logo-full.png"
        alt="PharmaLens"
        width={900}
        height={245}
        className={cn('w-auto select-none', size === 'sm' ? 'h-7' : size === 'lg' ? 'h-12' : 'h-9')}
        draggable={false}
      />
      {tagline && <p className="mt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-accent-700">Research intelligence</p>}
    </div>
  )
}
