import { useLayoutEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { STAT_COPY } from "../../copy/stats";

export default function StatTooltip({ id, value, children, className = "", showIcon = true }) {
  const copy = STAT_COPY[id];
  const tooltipId = useId();
  const triggerRef = useRef(null);
  const tooltipRef = useRef(null);
  const inputType = useRef(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useLayoutEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = Math.min(352, window.innerWidth - 16);
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      const height = tooltipRef.current?.getBoundingClientRect().height || 0;
      const roomBelow = window.innerHeight - rect.bottom - 8;
      const roomAbove = rect.top - 8;
      const top = roomBelow >= height || roomBelow >= roomAbove
        ? Math.min(rect.bottom + 8, window.innerHeight - height - 8)
        : Math.max(8, rect.top - height - 8);
      setPosition({ top: Math.max(8, top), left });
    };
    const dismiss = (event) => {
      if (!triggerRef.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    document.addEventListener("pointerdown", dismiss);
    document.addEventListener("keydown", escape);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      document.removeEventListener("pointerdown", dismiss);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  if (!copy) return children;
  const isEmpty = value == null || value === "—";
  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        aria-label={copy.label + ", explanation"}
        aria-describedby={open ? tooltipId : undefined}
        aria-expanded={open}
        className={`inline-flex items-center gap-1 text-left rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${className}`}
        onPointerDown={(event) => { inputType.current = event.pointerType; }}
        onMouseEnter={() => { if (inputType.current !== "touch") setOpen(true); }}
        onMouseLeave={() => { if (inputType.current !== "touch") setOpen(false); }}
        onFocus={() => { if (inputType.current !== "touch") setOpen(true); }}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((wasOpen) => inputType.current === "touch" ? !wasOpen : true)}
      >
        {children}
        {showIcon && <span aria-hidden="true" className="text-slate-500 text-xs normal-case tracking-normal">ⓘ</span>}
      </button>
      {open && createPortal(
        <div
          id={tooltipId}
          ref={tooltipRef}
          role="tooltip"
          className="fixed z-[100] w-[calc(100vw-1rem)] max-w-[22rem] max-h-[calc(100vh-1rem)] overflow-y-auto rounded-lg border border-surface-600 bg-surface-800 p-3 text-xs leading-relaxed text-slate-300 shadow-xl"
          style={{ left: position.left, top: position.top }}
        >
          <p className="font-semibold text-white mb-1">{copy.label}</p>
          <p>{isEmpty ? copy.empty : copy.what}</p>
          {!isEmpty && <><p className="mt-1">{copy.tells}</p><p className="mt-1 text-slate-400">{copy.excludes}</p></>}
        </div>,
        document.body
      )}
    </>
  );
}
