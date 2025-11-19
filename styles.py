POPUP_STYLES = """
<style>
      .al-popup {{
        font-family: Inter, Segoe UI, Roboto, Arial;
        font-size: 13px;
        color: #1f2937;
        background: #fff;
        border-radius: 12px;
        padding: 6px 12px 12px 12px;  /* 👈 solo 6px arriba */
        width: 520px;
        max-width: 520px;
        box-sizing: border-box;
        box-shadow: 0 6px 18px rgba(15,23,42,0.12);
      }}
      .al-popup .field {{
        margin-bottom: 8px;
      }}
      .al-popup .field label {{
        display: block;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 4px;
      }}

      .al-popup .field input,
      .al-popup .field select {{
        width: 100%;
        padding: 6px 8px;
        border-radius: 6px;
        border: 1px solid #d0d7de;
        font-size: 13px;
        box-sizing: border-box;
        background-color: #fff;
      }}
      .al-popup .field select {{
        cursor: pointer;
      }}
      .title {{
        font-weight:700;color:#0B5ED7;font-size:15px;
      }}
      .excel-btn {{
        display:inline-block;
        font-size:12px;
        font-weight:600;
        background:#f97316;      /* naranja */
        color:#ffffff !important; /* texto blanco, por encima de .al-popup a */
        padding:4px 10px;
        border-radius:999px;
        text-decoration:none;
        border:none;
        box-shadow:0 1px 3px rgba(0,0,0,0.15);
      }}
      .excel-btn:hover {{
        filter:brightness(0.95);
      }}

      .head {{
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:6px;
        gap:8px;
      }}
      .title-wrap {{
        display:flex;
        flex-direction:column;
        gap:2px;
      }}
      .head-right {{
        display:flex;
        flex-direction:column;
        align-items:flex-end;
        gap:4px;
      }}
      .badges {{
        display:flex;gap:6px;align-items:center;
      }}
      .badge {{
        background:#eef2ff;color:#0b4bd6;padding:4px 8px;
        border-radius:999px;font-weight:600;font-size:12px;
      }}
      .badge.count {{
        background:#0b5ed7;color:white;
      }}
      .sub {{
        color:#6b7280;font-size:12px;margin-bottom:6px;
      }}
      .plist {{
        list-style:none;padding:0;margin:6px 0 0 0;
        max-height:360px;overflow:auto;
      }}
      .pitem + .pitem {{
        margin-top:8px;
      }}
      .pdetails {{
        margin-top:6px;background:#fbfbff;border-radius:8px;
        padding:0;border:1px solid #eef2ff;
      }}
      .pdetails > summary {{
        list-style:none;
        cursor:pointer;
        padding:8px;
        border-radius:8px 8px 0 0;
      }}
      .pdetails[open] > summary {{
        border-bottom:1px solid #e5e7eb;
      }}
      .summary-row {{
        display:flex;gap:10px;align-items:center;
      }}
      .avatar {{
        width:32px;height:32px;border-radius:8px;
        background:linear-gradient(135deg,#7c3aed,#60a5fa);
        color:white;display:flex;align-items:center;
        justify-content:center;font-weight:700;font-size:13px;
      }}
      .meta {{
        flex:1;min-width:0;
      }}
      .name {{
        font-weight:700;color:#0b5ed7;white-space:nowrap;
        overflow:hidden;text-overflow:ellipsis;
      }}
      .mode-tags {{
        display:flex;gap:4px;margin-top:2px;font-size:11px;
      }}
      .tag-mode {{
        padding:2px 8px;border-radius:999px;
        border:1px solid #d1d5db;
        color:#4b5563;
      }}
      .tag-edit {{
        display:none;
        background:#0b5ed7;
        color:white;
        border-color:#0b5ed7;
      }}
      .pdetails[open] .tag-view {{
        display:none;
      }}
      .pdetails[open] .tag-edit {{
        display:inline-flex;
      }}
      .small {{
        font-size:12px;color:#374151;margin-top:4px;
      }}
      .block {{
        padding:8px;
      }}
      .extras {{
        font-size:13px;color:#374151;
      }}
      .extras b {{
        font-weight:600;
      }}
      .mat summary {{
        cursor:pointer;list-style:none;outline:none;
        font-weight:700;color:#0b5ed7;
      }}
      .mlist {{
        list-style:none;padding-left:12px;margin:6px 0 0 0;
        display:flex;flex-direction:column;gap:4px;
      }}
      .mitem {{
        background:#f1f5f9;padding:6px;border-radius:6px;
        font-size:12px;color:#0f1724;
      }}
      .no-mat {{
        margin-top:6px;color:#6b7280;font-size:13px;font-style:italic;
      }}
      .edit-panel-inner {{
        display:flex;flex-direction:column;gap:8px;
      }}
      .form-grid {{
        display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
        gap:6px 10px;margin-top:6px;
      }}
      .field {{
        display:flex;flex-direction:column;gap:3px;font-size:12px;
      }}
      .field.full {{
        margin-top:6px;
      }}
      .field label {{
        font-weight:600;color:#4b5563;
      }}
      .field input, .field textarea {{
        width:100%;font-size:12px;padding:5px 6px;
        border-radius:4px;border:1px solid #e5e7eb;
        box-sizing:border-box;
      }}
      .field textarea {{
        resize:vertical;
      }}
      .hint {{
        font-size:11px;color:#6b7280;margin-top:4px;font-style:italic;
      }}
      .leaflet-popup-content {{
          margin-top: 0 !important;
      }}
      .edit-toggle {{ display:none; }}        /* el checkbox NO se ve */
      .view-block {{ display:block; }}
      .edit-block {{ display:none; }}

      .edit-toggle:checked ~ .view-block {{ display:none; }}
      .edit-toggle:checked ~ .edit-block {{ display:block; }}
      .btn-icon,
      .save-btn {{
        font-size: 12px;
        border-radius: 999px;
        padding: 4px 10px;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;              /* espacio entre el icono y el texto */
        border: none;
      }}

      /* BOTÓN EDITAR (lápiz) */
      .edit-btn {{
        background: #eff6ff;       /* azul muy clarito */
        color: #1d4ed8;            /* azul intenso texto */
        border: 1px solid #bfdbfe; /* borde suave */
        font-weight: 600;
      }}

      .edit-btn:hover {{
        background: #dbeafe;
      }}
      /* BOTÓN CANCELAR (X) */
      .cancel-btn {{  
        background: #f3f4f6;
        color: #111827;
        border: 1px solid #e5e7eb;
      }}

      /* BOTÓN GUARDAR */
      .save-btn {{
        background: #10b981;
        color: #ffffff;
        font-weight: 600;
      }}
      .save-btn:hover {{
        filter: brightness(0.95);
      }}
      .al-popup .materias-list {{
        list-style: none;
        margin: 4px 0 0 0;
        padding: 0;
      }}
      .al-popup .materia-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 6px;
        border-radius: 4px;
        font-size: 13px;
      }}
      .al-popup .materia-row:nth-child(odd) {{
        background: #f6f8fa;
      }}

      .al-popup .materia-name {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}

      .al-popup .materia-actions {{
        display: flex;
        gap: 4px;
      }}

      .al-popup .icon-btn {{
        border: none;
        background: #e9ecef;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 12px;
        cursor: pointer;
      }}

      .al-popup .icon-btn:hover {{
        background: #d0d7de;
      }}
      .al-popup .materia-row.add-row {{
        justify-content: center;
      }}

      .al-popup .materia-row.add-row .icon-btn {{
        width: 100%;
        justify-content: center;
      }}

      .al-popup .materia-editor {{
        margin-top: 8px;
        padding: 8px;
        border-radius: 6px;
        background: #f6f8fa;
      }}
  
      </style>
"""