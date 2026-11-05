import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ExternalLink,
  FileSearch,
  FileText,
  FileUp,
  Loader2,
  RefreshCw,
  ScanText,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { analyzeText, errorMessage, getFilePiiFindings, getFiles, getOcrStatus, getPrivacyFindings, scanOcrDocument } from '../api';
import {
  Badge,
  btnPrimary,
  btnSecondary,
  Drawer,
  EmptyState,
  ErrorState,
  formatDateTime,
  formatNumber,
  formatScore,
  InlineNotice,
  KeyValue,
  labelClass,
  LoadingState,
  PageHeader,
  Panel,
  SearchInput,
  selectClass,
  StatCard,
  timeAgo,
} from '../components/ui';

const CATEGORY_TONE = { SAFE: 'green', SENSITIVE: 'amber', HIGH_RISK: 'red' };

export default function SensitiveFiles() {
  const [tab, setTab] = useState('files');
  const [files, setFiles] = useState([]);
  const [findings, setFindings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [fileQuery, setFileQuery] = useState('');
  const [findingCategory, setFindingCategory] = useState('');

  const [selectedFile, setSelectedFile] = useState(null);
  const [fileFindings, setFileFindings] = useState([]);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState('');

  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzeValue, setAnalyzeValue] = useState('');
  const [analyzeBusy, setAnalyzeBusy] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [scanMode, setScanMode] = useState('text');
  const [ocrFile, setOcrFile] = useState(null);
  const [ocrBusy, setOcrBusy] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [ocrStatus, setOcrStatus] = useState(null);
  const [ocrStatusLoading, setOcrStatusLoading] = useState(true);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError('');
      try {
        const [fileResult, findingResult] = await Promise.all([
          getFiles({ limit: 100 }),
          getPrivacyFindings({ limit: 200, category: findingCategory || undefined }),
        ]);
        setFiles(Array.isArray(fileResult) ? fileResult : []);
        setFindings(Array.isArray(findingResult) ? findingResult : []);
      } catch (err) {
        setError(errorMessage(err, 'Could not load file metadata or PII findings.'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [findingCategory],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    getOcrStatus()
      .then(setOcrStatus)
      .catch(() => setOcrStatus({ available: false }))
      .finally(() => setOcrStatusLoading(false));
  }, []);

  const metrics = useMemo(() => {
    const high = findings.filter((item) => item.category === 'HIGH_RISK').length;
    const sensitive = findings.filter((item) => item.category === 'SENSITIVE').length;
    const engines = [...new Set(findings.map((item) => item.engine).filter(Boolean))];
    return { high, sensitive, engines };
  }, [findings]);

  const visibleFiles = useMemo(() => {
    const needle = fileQuery.trim().toLowerCase();
    if (!needle) return files;
    return files.filter((file) =>
      [file.name, file.owner_email, file.mime_type, file.source]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle)),
    );
  }, [files, fileQuery]);

  const openFile = async (file) => {
    setSelectedFile(file);
    setFileFindings([]);
    setFileError('');
    setFileLoading(true);
    try {
      const result = await getFilePiiFindings(file.file_id);
      setFileFindings(Array.isArray(result) ? result : []);
    } catch (err) {
      setFileError(errorMessage(err, 'Could not load findings for this file.'));
    } finally {
      setFileLoading(false);
    }
  };

  const runAnalysis = async (event) => {
    event.preventDefault();
    setAnalyzeError('');
    setAnalyzeResult(null);
    setOcrResult(null);
    if (!analyzeValue.trim()) {
      setAnalyzeError('Enter text to analyse.');
      return;
    }
    setAnalyzeBusy(true);
    try {
      const result = await analyzeText(analyzeValue);
      setAnalyzeResult(result);
      setAnalyzeValue('');
      load({ silent: true });
    } catch (err) {
      setAnalyzeError(errorMessage(err, 'Privacy analysis failed.'));
    } finally {
      setAnalyzeBusy(false);
    }
  };

  const runOcrScan = async (event) => {
    event.preventDefault();
    setAnalyzeError('');
    setAnalyzeResult(null);
    setOcrResult(null);
    if (!ocrFile) {
      setAnalyzeError('Choose an image or PDF to scan.');
      return;
    }
    setOcrBusy(true);
    try {
      const result = await scanOcrDocument(ocrFile);
      setOcrResult(result);
      setOcrFile(null);
      load({ silent: true });
    } catch (err) {
      setAnalyzeError(errorMessage(err, 'OCR scan failed.'));
    } finally {
      setOcrBusy(false);
    }
  };

  const closeAnalyze = () => {
    setAnalyzeOpen(false);
    setAnalyzeValue('');
    setOcrFile(null);
    setAnalyzeError('');
    setAnalyzeResult(null);
    setOcrResult(null);
    setScanMode('text');
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Data protection"
        title="Sensitive files & PII findings"
        subtitle="Review cloud file metadata, run controlled text checks, or OCR a user-selected image/PDF. The app stores derived findings and risk results, not source content."
        actions={
          <>
            <button type="button" className={btnSecondary} onClick={() => load({ silent: true })} disabled={refreshing}>
              <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
              Refresh
            </button>
            <button type="button" className={btnSecondary} onClick={() => { setScanMode('text'); setAnalyzeOpen(true); setAnalyzeError(''); setAnalyzeResult(null); setOcrResult(null); }}>
              <ScanText size={15} />
              Analyse text
            </button>
            <button type="button" className={btnPrimary} onClick={() => { setScanMode('ocr'); setAnalyzeOpen(true); setAnalyzeError(''); setAnalyzeResult(null); setOcrResult(null); }}>
              <FileUp size={15} />
              Scan image/PDF
            </button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Cloud files loaded" value={formatNumber(files.length)} hint="Newest 100 metadata records" icon={FileText} tone="blue" loading={loading} />
        <StatCard label="High-risk findings" value={formatNumber(metrics.high)} hint="Score ≥ 60 in loaded findings" icon={ShieldAlert} tone="red" loading={loading} />
        <StatCard label="Sensitive findings" value={formatNumber(metrics.sensitive)} hint="Score 20–59 in loaded findings" icon={FileSearch} tone="amber" loading={loading} />
        <StatCard label="Detection engines" value={metrics.engines.length ? metrics.engines.join(', ') : '—'} hint="Engine recorded per finding" icon={ShieldCheck} tone="green" loading={loading} />
      </div>

      <div className="flex gap-1 border-b border-slate-800">
        {[
          ['files', `Cloud files (${files.length})`],
          ['findings', `PII findings (${findings.length})`],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`border-b-2 px-4 py-2.5 text-xs font-semibold transition ${
              tab === key ? 'border-blue-500 text-blue-300' : 'border-transparent text-slate-500 hover:text-slate-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'files' ? (
        <Panel
          title="Cloud file metadata"
          subtitle="Names, owners and URLs only. The endpoint agent does not read file contents."
          actions={<SearchInput value={fileQuery} onChange={setFileQuery} placeholder="Filter by file, owner or type" className="w-72" />}
          bodyClassName="p-0"
        >
          {loading ? (
            <LoadingState />
          ) : visibleFiles.length === 0 ? (
            <EmptyState
              icon={FileText}
              title={files.length === 0 ? 'No cloud file metadata' : 'No files match the filter'}
              message={
                files.length === 0
                  ? 'Metadata appears here after a configured SaaS/cloud connector synchronises file records. This page does not claim visibility into local file contents.'
                  : 'Adjust the text filter to see more records.'
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Owner</th>
                    <th>Type</th>
                    <th>Source</th>
                    <th>Modified</th>
                    <th>Retrieved</th>
                    <th className="text-right">Findings</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleFiles.map((file) => (
                    <tr key={file.file_id}>
                      <td>
                        <p className="font-medium text-slate-200">{file.name}</p>
                        <p className="truncate text-[10px] text-slate-500">{file.file_id}</p>
                      </td>
                      <td className="text-slate-400">{file.owner_email || '—'}</td>
                      <td className="text-slate-400">{file.mime_type || '—'}</td>
                      <td><Badge tone="purple">{file.source || 'unknown'}</Badge></td>
                      <td className="whitespace-nowrap text-slate-400">{file.modified_time ? formatDateTime(file.modified_time) : '—'}</td>
                      <td className="whitespace-nowrap text-slate-500">{file.retrieved_timestamp ? timeAgo(file.retrieved_timestamp) : '—'}</td>
                      <td className="text-right">
                        <button type="button" className={btnSecondary} onClick={() => openFile(file)}>Open</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      ) : (
        <Panel
          title="PII findings"
          subtitle="Derived metadata only. Raw text and matched values are not stored."
          actions={
            <select value={findingCategory} onChange={(event) => setFindingCategory(event.target.value)} className={`${selectClass} w-44`}>
              <option value="">All categories</option>
              <option value="SAFE">SAFE</option>
              <option value="SENSITIVE">SENSITIVE</option>
              <option value="HIGH_RISK">HIGH_RISK</option>
            </select>
          }
          bodyClassName="p-0"
        >
          {loading ? (
            <LoadingState />
          ) : findings.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No PII findings" message="Findings appear after controlled text or a user-selected image/PDF is scanned. No synthetic findings are displayed." />
          ) : (
            <div className="overflow-x-auto">
              <table className="soc-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Category</th>
                    <th>Score</th>
                    <th>Entities</th>
                    <th>Owner</th>
                    <th>File / event</th>
                    <th>Source</th>
                    <th>PII engine</th>
                    <th>OCR engine</th>
                  </tr>
                </thead>
                <tbody>
                  {findings.map((finding) => (
                    <tr key={finding.finding_id}>
                      <td className="whitespace-nowrap text-slate-400" title={formatDateTime(finding.timestamp)}>{timeAgo(finding.timestamp)}</td>
                      <td><Badge tone={CATEGORY_TONE[finding.category] || 'neutral'}>{finding.category}</Badge></td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-slate-200">{formatScore(finding.sensitivity_score, 0)}</span>
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-800">
                            <div className={`h-full ${finding.sensitivity_score >= 60 ? 'bg-red-500' : finding.sensitivity_score >= 20 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${Math.min(100, Number(finding.sensitivity_score) || 0)}%` }} />
                          </div>
                        </div>
                      </td>
                      <td className="max-w-[18rem] text-[11px] text-slate-400">
                        {(finding.entities || []).length === 0
                          ? 'None retained'
                          : finding.entities.map((entity) => `${entity.entity_type} ×${entity.count}`).join(', ')}
                      </td>
                      <td className="text-slate-400">{finding.user_id}</td>
                      <td className="max-w-[12rem] truncate text-[11px] text-slate-500" title={finding.file_id || finding.event_id || ''}>{finding.file_id || finding.event_id || '—'}</td>
                      <td><Badge tone={finding.source === 'ocr_upload' ? 'purple' : 'blue'}>{finding.source === 'ocr_upload' ? 'OCR upload' : 'Text sample'}</Badge></td>
                      <td><Badge tone={finding.engine === 'presidio' ? 'green' : 'amber'}>{finding.engine}</Badge></td>
                      <td className="text-[11px] text-slate-400">{finding.ocr_engine || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      )}

      <InlineNotice tone={ocrStatusLoading || ocrStatus?.available ? 'info' : 'warning'}>
        <strong>{ocrStatusLoading ? 'Checking OCR readiness:' : ocrStatus?.available ? 'Content scan scope:' : 'OCR is not configured:'}</strong>{' '}
        {ocrStatusLoading
          ? 'Checking whether the local OCR engine is available.'
          : ocrStatus?.available
          ? 'Endpoint monitoring remains metadata-only. OCR runs only when a signed-in user selects a file here; the original document and extracted text are discarded after the request.'
          : 'Install the optional OCR Python packages and Tesseract executable to enable image and scanned-PDF scans. Existing metadata and text analysis remain available.'}
      </InlineNotice>

      <Drawer open={Boolean(selectedFile)} onClose={() => setSelectedFile(null)} title={selectedFile?.name || 'File details'} subtitle={selectedFile?.file_id}>
        {selectedFile ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Owner">{selectedFile.owner_email || '—'}</KeyValue>
              <KeyValue label="MIME type">{selectedFile.mime_type || '—'}</KeyValue>
              <KeyValue label="Source">{selectedFile.source || '—'}</KeyValue>
              <KeyValue label="Created">{selectedFile.created_time ? formatDateTime(selectedFile.created_time) : '—'}</KeyValue>
              <KeyValue label="Modified">{selectedFile.modified_time ? formatDateTime(selectedFile.modified_time) : '—'}</KeyValue>
              <KeyValue label="Retrieved">{selectedFile.retrieved_timestamp ? formatDateTime(selectedFile.retrieved_timestamp) : '—'}</KeyValue>
              <KeyValue label="Web URL" className="col-span-2">
                {selectedFile.web_url && /^https?:\/\//i.test(selectedFile.web_url) ? (
                  <a href={selectedFile.web_url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300">
                    Open in provider <ExternalLink size={12} />
                  </a>
                ) : '—'}
              </KeyValue>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-bold text-slate-100">Derived findings ({fileFindings.length})</h3>
              {fileLoading ? (
                <LoadingState label="Loading file findings…" />
              ) : fileError ? (
                <ErrorState message={fileError} onRetry={() => openFile(selectedFile)} />
              ) : fileFindings.length === 0 ? (
                <p className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs text-slate-500">
                  No PII findings are linked to this file. That does not mean the file is safe; content
                  may not have been analysed.
                </p>
              ) : (
                <div className="space-y-2">
                  {fileFindings.map((finding) => (
                    <div key={finding.finding_id} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                      <div className="flex items-center justify-between">
                        <Badge tone={CATEGORY_TONE[finding.category] || 'neutral'}>{finding.category}</Badge>
                        <span className="font-mono text-xs text-slate-200">{finding.sensitivity_score}/100</span>
                      </div>
                      <p className="mt-1.5 text-[11px] text-slate-400">
                        {(finding.entities || []).map((entity) => `${entity.entity_type} ×${entity.count} (${entity.sensitivity})`).join(', ') || 'No entities retained'}
                      </p>
                      <p className="mt-1 text-[10px] text-slate-500">{formatDateTime(finding.timestamp)} · engine {finding.engine}</p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        ) : null}
      </Drawer>

      <Drawer
        open={analyzeOpen}
        onClose={closeAnalyze}
        title={scanMode === 'ocr' ? 'Scan an image or PDF' : 'Analyse controlled text'}
        subtitle="The scan is performed by the local API. Raw content and matched values are discarded; derived findings are retained."
      >
        <form onSubmit={scanMode === 'ocr' ? runOcrScan : runAnalysis} className="space-y-4">
          <div className="flex rounded-lg border border-slate-800 bg-slate-950/50 p-1">
            {[
              ['text', 'Text sample'],
              ['ocr', 'Image / PDF OCR'],
            ].map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => { setScanMode(mode); setAnalyzeError(''); setOcrResult(null); setAnalyzeResult(null); }}
                className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold transition ${scanMode === mode ? 'bg-blue-500/15 text-blue-200' : 'text-slate-500 hover:text-slate-200'}`}
              >
                {label}
              </button>
            ))}
          </div>
          <InlineNotice tone="warning">
            Use only content you are authorised to process. The API scans the selected content for this request, then stores entity types, counts and risk scores. It does not retain the uploaded file, OCR text or matched values.
          </InlineNotice>
          {scanMode === 'text' ? (
            <div>
              <label htmlFor="analyze-text" className={labelClass}>Text to analyse</label>
              <textarea
                id="analyze-text"
                rows={10}
                value={analyzeValue}
                onChange={(event) => setAnalyzeValue(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-950/70 p-3 font-mono text-xs text-slate-100 outline-none focus:border-blue-500"
                placeholder="Paste a controlled sample containing synthetic PII…"
                maxLength={100000}
              />
              <p className="mt-1 text-[10px] text-slate-500">{analyzeValue.length.toLocaleString()} characters. The request body is not echoed in the UI.</p>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 p-4">
              <label htmlFor="ocr-upload" className={labelClass}>Image or scanned document</label>
              <input
                id="ocr-upload"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,application/pdf,image/png,image/jpeg,image/tiff,image/bmp,image/webp"
                onChange={(event) => { setOcrFile(event.target.files?.[0] || null); setOcrResult(null); }}
                className="block w-full text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-slate-200 hover:file:bg-slate-700"
                disabled={ocrStatusLoading || !ocrStatus?.available || ocrBusy}
              />
              <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                PDF or PNG, JPEG, TIFF, BMP and WebP.
                {ocrStatus ? ` Up to ${formatNumber(Math.ceil(ocrStatus.max_file_bytes / (1024 * 1024)))} MiB and ${formatNumber(ocrStatus.max_pdf_pages)} PDF pages.` : ''}
                {' '}OCR requires the local Tesseract engine.
              </p>
              {ocrFile ? <p className="mt-2 text-xs text-slate-300">Selected: {ocrFile.name} · {formatNumber(Math.ceil(ocrFile.size / 1024))} KB</p> : null}
              {ocrStatusLoading ? <p className="mt-2 text-xs text-slate-500">Checking backend OCR readiness…</p> : null}
              {ocrStatus && !ocrStatus.available ? <p className="mt-2 text-xs text-amber-300">OCR engine is not available on the backend.</p> : null}
            </div>
          )}

          {analyzeError ? <p className="rounded-lg border border-red-900/50 bg-red-950/20 p-3 text-xs text-red-200">{analyzeError}</p> : null}

          {(analyzeResult || ocrResult) ? (() => {
            const resultFinding = ocrResult?.finding || analyzeResult;
            return (
            <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-100">Analysis result</h3>
                <Badge tone={CATEGORY_TONE[resultFinding.category] || 'neutral'}>{resultFinding.category}</Badge>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <KeyValue label="Sensitivity score">{resultFinding.sensitivity_score}/100</KeyValue>
                <KeyValue label="PII engine">{resultFinding.engine}</KeyValue>
                <KeyValue label="Source">{resultFinding.source === 'ocr_upload' ? 'Image/PDF OCR' : 'Text sample'}</KeyValue>
                {ocrResult ? <KeyValue label="OCR engine">{resultFinding.ocr_engine || ocrResult.ocr_engine}</KeyValue> : null}
                {ocrResult ? <KeyValue label="Pages scanned">{formatNumber(resultFinding.page_count || ocrResult.page_count)}</KeyValue> : null}
                <KeyValue label="Text length">{formatNumber(resultFinding.text_length)}</KeyValue>
                <KeyValue label="Finding ID"><span className="break-all font-mono text-[10px]">{resultFinding.finding_id}</span></KeyValue>
                {ocrResult?.risk_assessment ? (
                  <KeyValue label="Combined risk">{formatScore(ocrResult.risk_assessment.combined_score, 1)} · {ocrResult.risk_assessment.risk_category}</KeyValue>
                ) : null}
              </div>
              <div className="mt-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Entity types</p>
                {(resultFinding.entities || []).length === 0 ? (
                  <p className="mt-1 text-xs text-slate-500">No supported entity types detected.</p>
                ) : (
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    {resultFinding.entities.map((entity) => (
                      <Badge key={entity.entity_type} tone={entity.sensitivity === 'HIGH' ? 'red' : entity.sensitivity === 'MODERATE' ? 'amber' : 'neutral'}>
                        {entity.entity_type} ×{entity.count}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
          })() : null}

          <div className="flex justify-end gap-2 border-t border-slate-800 pt-4">
            <button type="button" className={btnSecondary} onClick={closeAnalyze}>Close</button>
            <button type="submit" className={btnPrimary} disabled={scanMode === 'ocr' ? ocrBusy || ocrStatusLoading || !ocrStatus?.available : analyzeBusy}>
              {(scanMode === 'ocr' ? ocrBusy : analyzeBusy) ? <Loader2 size={15} className="animate-spin" /> : scanMode === 'ocr' ? <FileUp size={15} /> : <ScanText size={15} />}
              {scanMode === 'ocr' ? 'Scan document' : 'Run analysis'}
            </button>
          </div>
        </form>
      </Drawer>
    </div>
  );
}
