import React from 'react'
export default function Button({children, className='', variant='primary', ...rest}){ return <button {...rest} className={`button button-${variant} ${className}`}>{children}</button> }
