import React from 'react'

export default function EpicVMMark({ size = 38, className = '', title = 'EpicVM' }) {
  return <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 64 64"
    fill="none"
    role="img"
    aria-labelledby="epicvm-mark-title"
    xmlns="http://www.w3.org/2000/svg"
  >
    <title id="epicvm-mark-title">{title}</title>
    <path d="M10 8H54V56H10V8Z" stroke="currentColor" strokeWidth="5" strokeLinejoin="miter" />
    <path d="M18 18H40M18 32H36M18 46H40" stroke="currentColor" strokeWidth="5" strokeLinecap="square" />
    <path d="M39 18L48 32L39 46M48 32H56" stroke="currentColor" strokeWidth="5" strokeLinecap="square" strokeLinejoin="miter" />
  </svg>
}
