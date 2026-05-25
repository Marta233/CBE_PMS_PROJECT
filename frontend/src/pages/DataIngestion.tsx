// DataIngestion.tsx  —  Upload BSC, JD, LOS files to the backend ingestion pipeline

import { useState, useRef, useCallback } from 'react';
import {
  Upload, FileText, CheckCircle, AlertCircle, X,
  CloudUpload, RefreshCw, Info, Trash2, ChevronDown, ChevronUp,
  Database, Layers, BookOpen, BarChart2,
} from 'lucide-react';
import Layout from '../components/Layout';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

// ── Types ─────────────────────────────────────────────────────────────────────
type DocType = 'BSC' | 'JD' | 'LOS';
type FileStatus = 'idle' | 'uploading' | 'success' | 'error';

interface SelectedFile {
  id:       string;
  file:     File;
  docType:  DocType;
  status:   FileStatus;
  message:  string;
  progress: number;
}

interface IngestResult {
  filename:    string;
  doc_type:    string;
  chunks:      number;
  status:      string;
  detail?:     string;
}

// ── Doc type config ───────────────────────────────────────────────────────────
const DOC_CONFIGS: Record<DocType, {
  label:       string;
  description: string;
  icon:        React.ElementType;
  color:       string;
  bgColor:     string;
  borderColor: string;
  accepts:     string;
  hint:        string;
}> = {
  BSC: {
    label:       'Balanced Scorecard (BSC)',
    description: 'KPI targets and strategic objectives by division',
    icon:        BarChart2,
    color:       'text-blue-700',
    bgColor:     'bg-blue-50 dark:bg-blue-900/20',
    borderColor: 'border-blue-200 dark:border-blue-800',
    accepts:     '.xlsx,.xls,.csv,.pdf',
    hint:        'Excel, CSV, or PDF — one file per division or combined',
  },
  JD: {
    label:       'Job Description (JD)',
    description: 'Role responsibilities, objectives, and job grades',
    icon:        BookOpen,
    color:       'text-purple-700',
    bgColor:     'bg-purple-50 dark:bg-purple-900/20',
    borderColor: 'border-purple-200 dark:border-purple-800',
    accepts:     '.pdf,.docx,.doc,.txt',
    hint:        'PDF or Word — one file per unit or combined',
  },
  LOS: {
    label:       'Line of Sight (LOS)',
    description: 'Cascaded department-level objectives per perspective',
    icon:        Layers,
    color:       'text-emerald-700',
    bgColor:     'bg-emerald-50 dark:bg-emerald-900/20',
    borderColor: 'border-emerald-200 dark:border-emerald-800',
    accepts:     '.xlsx,.xls,.csv,.pdf',
    hint:        'Excel or CSV with perspective, objective columns',
  },
};

function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }
function fmtSize(bytes: number) {
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Upload zone for one doc type ──────────────────────────────────────────────
function DropZone({
  docType,
  files,
  onAdd,
  onRemove,
}: {
  docType:  DocType;
  files:    SelectedFile[];
  onAdd:    (docType: DocType, newFiles: File[]) => void;
  onRemove: (id: string) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cfg = DOC_CONFIGS[docType];
  const Icon = cfg.icon;

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    if (dropped.length) onAdd(docType, dropped);
  }, [docType, onAdd]);

  const handleInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    if (picked.length) onAdd(docType, picked);
    e.target.value = '';
  };

  return (
    <div className={`rounded-xl border ${cfg.borderColor} ${cfg.bgColor} overflow-hidden`}>
      {/* Header */}
      <div className={`px-5 py-3.5 flex items-center gap-3 border-b ${cfg.borderColor}`}>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${cfg.bgColor} border ${cfg.borderColor}`}>
          <Icon size={16} className={cfg.color} />
        </div>
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{cfg.description}</p>
        </div>
        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 text-slate-500">
          {files.length} file{files.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Drop area */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`mx-4 my-3 border-2 border-dashed rounded-xl flex flex-col items-center justify-center py-6 cursor-pointer transition-all duration-200 ${
          dragOver
            ? 'border-current scale-[1.01] bg-white/60 dark:bg-slate-700/60'
            : 'border-slate-200 dark:border-slate-600 hover:border-current hover:bg-white/40 dark:hover:bg-slate-700/40'
        }`}
      >
        <CloudUpload size={22} className={`mb-2 ${dragOver ? cfg.color : 'text-slate-400'} transition-colors`} />
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
          Drop files here or <span className={`${cfg.color} underline underline-offset-2`}>browse</span>
        </p>
        <p className="text-xs text-slate-400 mt-1">{cfg.hint}</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={cfg.accepts}
          className="hidden"
          onChange={handleInput}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="px-4 pb-4 space-y-2">
          {files.map(f => (
            <div key={f.id}
              className="flex items-center gap-3 bg-white dark:bg-slate-800 rounded-lg px-3 py-2.5 border border-slate-100 dark:border-slate-700">
              <FileText size={15} className="text-slate-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{f.file.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-slate-400">{fmtSize(f.file.size)}</span>
                  {f.status === 'uploading' && (
                    <span className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                      <RefreshCw size={10} className="animate-spin" /> Uploading…
                    </span>
                  )}
                  {f.status === 'success' && (
                    <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                      <CheckCircle size={10} /> {f.message}
                    </span>
                  )}
                  {f.status === 'error' && (
                    <span className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
                      <AlertCircle size={10} /> {f.message}
                    </span>
                  )}
                </div>
                {f.status === 'uploading' && (
                  <div className="mt-1.5 h-1 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 rounded-full transition-all duration-300"
                      style={{ width: `${f.progress}%` }} />
                  </div>
                )}
              </div>
              {f.status !== 'uploading' && (
                <button onClick={() => onRemove(f.id)}
                  className="p-1 rounded text-slate-300 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors flex-shrink-0">
                  <X size={13} />
                </button>
              )}
              {f.status === 'success' && (
                <CheckCircle size={15} className="text-green-500 flex-shrink-0" />
              )}
              {f.status === 'error' && (
                <AlertCircle size={15} className="text-red-500 flex-shrink-0" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Result log panel ──────────────────────────────────────────────────────────
function ResultLog({ results }: { results: IngestResult[] }) {
  const [open, setOpen] = useState(true);
  if (!results.length) return null;
  const ok  = results.filter(r => r.status === 'success').length;
  const err = results.filter(r => r.status === 'error').length;

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-700/40 transition-colors">
        <div className="flex items-center gap-3">
          <Database size={16} className="text-slate-500" />
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Ingestion Results</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">{ok} success</span>
          {err > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-600">{err} failed</span>}
        </div>
        {open ? <ChevronUp size={15} className="text-slate-400" /> : <ChevronDown size={15} className="text-slate-400" />}
      </button>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-700/50">
                <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">File</th>
                <th className="text-left px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Type</th>
                <th className="text-left px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Chunks</th>
                <th className="text-left px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-3 py-2.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {results.map((r, i) => (
                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <FileText size={13} className="text-slate-400 flex-shrink-0" />
                      <span className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate max-w-[180px]">{r.filename}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      r.doc_type === 'BSC' ? 'bg-blue-100 text-blue-700' :
                      r.doc_type === 'JD'  ? 'bg-purple-100 text-purple-700' :
                      'bg-emerald-100 text-emerald-700'
                    }`}>
                      {r.doc_type}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                      {r.chunks ?? '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    {r.status === 'success'
                      ? <span className="inline-flex items-center gap-1 text-xs text-green-600"><CheckCircle size={12}/> Ingested</span>
                      : <span className="inline-flex items-center gap-1 text-xs text-red-600"><AlertCircle size={12}/> Failed</span>
                    }
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-xs text-slate-500 dark:text-slate-400">{r.detail ?? '—'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
export default function DataIngestion() {
  const [files,      setFiles]      = useState<SelectedFile[]>([]);
  const [uploading,  setUploading]  = useState(false);
  const [results,    setResults]    = useState<IngestResult[]>([]);
  const [globalErr,  setGlobalErr]  = useState<string | null>(null);

  // rebuild index after ingest
  const [rebuilding, setRebuilding] = useState(false);
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null);

  function addFiles(docType: DocType, newFiles: File[]) {
    const entries: SelectedFile[] = newFiles.map(f => ({
      id: uid(), file: f, docType, status: 'idle', message: '', progress: 0,
    }));
    setFiles(prev => [...prev, ...entries]);
  }

  function removeFile(id: string) {
    setFiles(prev => prev.filter(f => f.id !== id));
  }

  function clearAll() {
    setFiles([]);
    setResults([]);
    setGlobalErr(null);
    setRebuildMsg(null);
  }

  const idleFiles = files.filter(f => f.status === 'idle');

  // ── Upload all idle files sequentially ────────────────────────────────────
  async function handleIngest() {
    if (!idleFiles.length) return;
    setUploading(true);
    setGlobalErr(null);
    setResults([]);

    const newResults: IngestResult[] = [];

    for (const sf of idleFiles) {
      // mark uploading
      setFiles(prev => prev.map(f =>
        f.id === sf.id ? { ...f, status: 'uploading', progress: 10 } : f
      ));

      const formData = new FormData();
      formData.append('file',     sf.file);
      formData.append('doc_type', sf.docType);

      try {
        // simulate progress ticks while fetching
        const tick = setInterval(() => {
          setFiles(prev => prev.map(f =>
            f.id === sf.id && f.progress < 85
              ? { ...f, progress: f.progress + 15 }
              : f
          ));
        }, 400);

        const res = await fetch(`${API_URL}/api/ingest`, {
          method: 'POST',
          body:   formData,
        });

        clearInterval(tick);

        if (!res.ok) {
          let detail = '';
          try { detail = (await res.json()).detail ?? ''; } catch { detail = await res.text().catch(() => ''); }
          throw new Error(`${res.status}: ${detail || res.statusText}`);
        }

        const data: IngestResult = await res.json();
        newResults.push(data);
        setFiles(prev => prev.map(f =>
          f.id === sf.id
            ? { ...f, status: 'success', progress: 100, message: `${data.chunks} chunks indexed` }
            : f
        ));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        newResults.push({ filename: sf.file.name, doc_type: sf.docType, chunks: 0, status: 'error', detail: msg });
        setFiles(prev => prev.map(f =>
          f.id === sf.id ? { ...f, status: 'error', progress: 0, message: msg } : f
        ));
      }
    }

    setResults(newResults);
    setUploading(false);
  }

  // ── Rebuild FAISS index ────────────────────────────────────────────────────
  async function handleRebuild() {
    setRebuilding(true);
    setRebuildMsg(null);
    try {
      const res = await fetch(`${API_URL}/api/rebuild-index`, { method: 'POST' });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setRebuildMsg(data.message ?? 'Index rebuilt successfully.');
    } catch (err) {
      setRebuildMsg(`Failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setRebuilding(false);
    }
  }

  const totalFiles    = files.length;
  const successCount  = files.filter(f => f.status === 'success').length;
  const errorCount    = files.filter(f => f.status === 'error').length;

  return (
    <Layout title="Data Ingestion" subtitle="Upload BSC, JD, and LOS documents to the knowledge base">

      {/* ── Info banner ─────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20 px-5 py-4 mb-6 flex items-start gap-3">
        <Info size={16} className="text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-blue-800 dark:text-blue-200 mb-1">
            How ingestion works
          </p>
          <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
            Each file is parsed, chunked, and embedded into the FAISS vector store used by the LLM objective generator.
            Upload <strong>BSC</strong> for KPI targets, <strong>JD</strong> for job responsibilities, and <strong>LOS</strong> for cascaded strategic objectives.
            After uploading, click <strong>Rebuild Index</strong> to make new documents available to the generation pipeline.
          </p>
        </div>
      </div>

      {/* ── Stats row ───────────────────────────────────────────────────── */}
      {totalFiles > 0 && (
        <div className="grid grid-cols-4 gap-4 mb-5">
          {[
            { label: 'Total Files',  value: totalFiles,   color: 'text-slate-800 dark:text-white'  },
            { label: 'Ready',        value: idleFiles.length, color: 'text-blue-600'               },
            { label: 'Ingested',     value: successCount, color: 'text-green-600'                  },
            { label: 'Failed',       value: errorCount,   color: 'text-red-600'                    },
          ].map((s, i) => (
            <div key={i} className="card p-4">
              <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Three drop zones ────────────────────────────────────────────── */}
      <div className="space-y-4 mb-6">
        {(['BSC', 'JD', 'LOS'] as DocType[]).map(dt => (
          <DropZone
            key={dt}
            docType={dt}
            files={files.filter(f => f.docType === dt)}
            onAdd={addFiles}
            onRemove={removeFile}
          />
        ))}
      </div>

      {/* ── Error banner ─────────────────────────────────────────────────  */}
      {globalErr && (
        <div className="mb-5 rounded-xl border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2.5 bg-red-100 dark:bg-red-900/50 border-b border-red-200 dark:border-red-800">
            <AlertCircle size={14} className="text-red-600" />
            <span className="text-sm font-semibold text-red-700 dark:text-red-300">Error</span>
            <button onClick={() => setGlobalErr(null)} className="ml-auto text-red-400 hover:text-red-600">
              <X size={13} />
            </button>
          </div>
          <p className="px-4 py-3 text-xs text-red-700 dark:text-red-300 font-mono whitespace-pre-wrap">{globalErr}</p>
        </div>
      )}

      {/* ── Action bar ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap mb-6">
        {/* Ingest */}
        <button
          onClick={handleIngest}
          disabled={!idleFiles.length || uploading}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading
            ? <><svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>Ingesting…</>
            : <><Upload size={15}/>Ingest {idleFiles.length > 0 ? `${idleFiles.length} File${idleFiles.length > 1 ? 's' : ''}` : 'Files'}</>
          }
        </button>

        {/* Rebuild index */}
        <button
          onClick={handleRebuild}
          disabled={rebuilding || uploading}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg border border-slate-200 dark:border-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={15} className={rebuilding ? 'animate-spin' : ''} />
          {rebuilding ? 'Rebuilding…' : 'Rebuild Index'}
        </button>

        {/* Clear */}
        {files.length > 0 && !uploading && (
          <button
            onClick={clearAll}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-white dark:bg-slate-700 text-red-600 text-sm font-medium rounded-lg border border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
          >
            <Trash2 size={15} />Clear All
          </button>
        )}

        {/* Rebuild status */}
        {rebuildMsg && (
          <span className={`text-xs font-medium px-3 py-1.5 rounded-lg border ${
            rebuildMsg.startsWith('Failed')
              ? 'bg-red-50 text-red-700 border-red-200'
              : 'bg-green-50 text-green-700 border-green-200'
          }`}>
            {rebuildMsg.startsWith('Failed') ? '✗' : '✓'} {rebuildMsg}
          </span>
        )}
      </div>

      {/* ── Results log ──────────────────────────────────────────────────── */}
      <ResultLog results={results} />

      {/* ── Empty state ──────────────────────────────────────────────────── */}
      {files.length === 0 && (
        <div className="card p-12 text-center mt-2">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
            style={{ backgroundColor: 'rgba(137,45,143,0.08)' }}>
            <Database size={28} style={{ color: '#892d8f' }} />
          </div>
          <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100 mb-2">No Files Selected</h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
            Use the drop zones above to add your <strong>BSC</strong>, <strong>JD</strong>, and <strong>LOS</strong> files.
            You can drag and drop or click to browse. Once uploaded, click <strong>Rebuild Index</strong> to make them available to the generation pipeline.
          </p>
        </div>
      )}
    </Layout>
  );
}
