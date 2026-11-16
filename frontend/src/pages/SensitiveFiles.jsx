import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Cpu,
  Database,
  Download,
  FileSearch,
  FileText,
  FileUp,
  Layers,
  Loader2,
  RefreshCw,
  ScanText,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import {
  analyzeText,
  downloadDriveFile,
  errorMessage,
  getFileAnalysisSummary,
  getFilePiiFindings,
  getFiles,
  getOcrStatus,
  getPrivacyFindings,
  getSimilarFiles,
  runOfflineAnalysis,
  scanOcrDocument,
  syncDriveFiles,
} from '../api';
import { useAuth } from '../context/AuthContext';
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
  const { user } = useAuth();
  const [tab, setTab] = useState('files');
  const [files, setFiles] = useState([]);
  const [findings, setFindings] = useState([]);
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [fileQuery, setFileQuery] = useState('');
  const [findingCategory, setFindingCategory] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [downloadError, setDownloadError] = useState('');
  const [offlineBusy, setOfflineBusy] = useState(false);
  const [offlineNotice, setOfflineNotice] = useState('');

  const [selectedFile, setSelectedFile] = useState(null);
  const [fileFindings, setFileFindings] = useState([]);
  const [similarFiles, setSimilarFiles] = useState([]);
  const [fileLoading, setFileLoading] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
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
        const [fileResult, findingResult, summaryResult] = await Promise.all([
          getFiles({ limit: 100 }),
          getPrivacyFindings({ limit: 200, category: findingCategory || undefined }),
          getFileAnalysisSummary().catch(() => null),
        ]);
        setFiles(Array.isArray(fileResult) ? fileResult : []);
        setFindings(Array.isArray(findingResult) ? findingResult : []);
        if (summaryResult) setAnalysisSummary(summaryResult);
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
    setSimilarFiles([]);
    setFileError('');
    setFileLoading(true);
    setSimilarLoading(true);
    try {
      const [fFindings, simFiles] = await Promise.all([
        getFilePiiFindings(file.file_id).catch(() => []),
        getSimilarFiles(file.file_id).catch(() => []),
      ]);
      setFileFindings(Array.isArray(fFindings) ? fFindings : []);
      setSimilarFiles(Array.isArray(simFiles) ? simFiles : []);
    } catch (err) {
      setFileError(errorMessage(err, 'Could not load findings for this file.'));
    } finally {
      setFileLoading(false);
      setSimilarLoading(false);
    }
  };

  const syncFiles = async () => {
    setSyncing(true);
    setError('');
    try {
      await syncDriveFiles();
      await load({ silent: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not synchronize Google Drive metadata.'));
    } finally {
      setSyncing(false);
    }
  };

  const triggerOfflineAnalysis = async (force = false) => {
    setOfflineBusy(true);
    setOfflineNotice('');
    setError('');
    try {
      const res = await runOfflineAnalysis({ force });
      setOfflineNotice(
        `Offline analysis complete: ${res.processed} processed, ${res.skipped} unchanged (skipped), ${res.failed} failed. Sensitive files: ${res.sensitive_count}.`
      );
      await load({ silent: true });
    } catch (err) {
      setError(errorMessage(err, 'Offline cloud analysis failed.'));
    } finally {
      setOfflineBusy(false);
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
        <div className="space-y-4">
          {/* Offline Cloud Content Analysis & Vector Index Panel */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/60 p-4 shadow-sm backdrop-blur">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                  <Database size={16} />
                </div>
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
                    Offline Cloud Content Analysis & Vector Index
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Phase 1 Pipeline: Deep PII extraction (.txt, .docx, .xlsx, .pdf, OCR), incremental caching, and safe vector representation.
                  </p>
                </div>
              </div>
              {['ADMIN', 'USER'].includes(user?.role) ? (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className={btnSecondary}
                    onClick={() => triggerOfflineAnalysis(true)}
                    disabled={offlineBusy}
                    title="Re-run deep content inspection across all cloud documents"
                  >
                    <RefreshCw size={13} className={offlineBusy ? 'animate-spin' : ''} />
                    Force Re-analyze All
                  </button>
                  <button
                    type="button"
                    className={btnPrimary}
                    onClick={() => triggerOfflineAnalysis(false)}
                    disabled={offlineBusy}
                  >
                    {offlineBusy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    {offlineBusy ? 'Analyzing Cloud Content…' : 'Run Offline Analysis'}
                  </button>
                </div>
              ) : null}
            </div>

            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 text-xs">
              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border border-slate-200/60 dark:border-slate-800">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Content Analyzed</p>
                <p className="mt-0.5 text-base font-bold text-slate-900 dark:text-slate-100">
                  {analysisSummary ? `${analysisSummary.completed} / ${analysisSummary.total}` : `${files.filter((f) => f.analysis_status === 'COMPLETED').length} / ${files.length}`}
                </p>
                <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                  {analysisSummary?.pending ?? files.filter((f) => !f.analysis_status || f.analysis_status === 'PENDING').length} pending
                </p>
              </div>

              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border border-slate-200/60 dark:border-slate-800">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Sensitive Files</p>
                <p className="mt-0.5 text-base font-bold text-amber-600 dark:text-amber-400">
                  {analysisSummary?.sensitive_count ?? files.filter((f) => (f.sensitivity_score || 0) >= 20).length}
                </p>
                <p className="text-[10px] text-red-500 dark:text-red-400 font-medium">
                  {analysisSummary?.high_risk_count ?? files.filter((f) => (f.sensitivity_score || 0) >= 60).length} high risk
                </p>
              </div>

              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border border-slate-200/60 dark:border-slate-800">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Analysis Failures</p>
                <p className="mt-0.5 text-base font-bold text-slate-900 dark:text-slate-100">
                  {analysisSummary?.failed ?? files.filter((f) => f.analysis_status === 'FAILED').length}
                </p>
                <p className="text-[10px] text-slate-400">unreadable format</p>
              </div>

              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border border-slate-200/60 dark:border-slate-800">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Vector Store</p>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <Badge tone="purple">
                    {analysisSummary?.vector_status?.provider === 'pinecone' ? 'Pinecone' : 'Local Vector Store'}
                  </Badge>
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">
                  {analysisSummary?.vector_status?.total_indexed ?? 0} metadata vectors
                </p>
              </div>

              <div className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border border-slate-200/60 dark:border-slate-800">
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Last Cloud Analysis</p>
                <p className="mt-0.5 truncate text-xs font-semibold text-slate-900 dark:text-slate-100" title={analysisSummary?.last_analysis_time ? formatDateTime(analysisSummary.last_analysis_time) : 'Never'}>
                  {analysisSummary?.last_analysis_time ? timeAgo(analysisSummary.last_analysis_time) : 'Never'}
                </p>
                <p className="text-[10px] text-slate-400">incremental delta</p>
              </div>
            </div>

            {offlineNotice ? (
              <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2.5 text-xs text-emerald-700 dark:text-emerald-300">
                {offlineNotice}
              </div>
            ) : null}
          </div>

          <Panel
            title="Cloud file metadata & content analysis"
            subtitle="Shared Google Drive folder. Downloads are mediated and authorized by the backend."
            actions={
              <div className="flex gap-2">
                {user?.role === 'ADMIN' ? (
                  <button className={btnSecondary} onClick={syncFiles} disabled={syncing}>
                    <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} /> Sync Drive
                  </button>
                ) : null}
                <SearchInput value={fileQuery} onChange={setFileQuery} placeholder="Filter by file, owner or type" className="w-72" />
              </div>
            }
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
                    ? 'No synchronized Google Drive files are available. An administrator can synchronize the configured shared folder.'
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
                      <th>Content Analysis</th>
                      <th>Source</th>
                      <th>Modified</th>
                      <th>Size</th>
                      <th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleFiles.map((file) => {
                      const status = file.analysis_status || 'PENDING';
                      const score = file.sensitivity_score;
                      const tier = file.sensitivity_tier;

                      return (
                        <tr key={file.file_id}>
                          <td>
                            <p className="font-semibold text-slate-900 dark:text-slate-100">{file.name}</p>
                            <p className="truncate text-[10px] text-slate-500 dark:text-slate-400">{file.file_id}</p>
                          </td>
                          <td className="text-slate-600 dark:text-slate-400">{file.owner_email || '—'}</td>
                          <td className="text-slate-600 dark:text-slate-400">{file.mime_type || '—'}</td>
                          <td>
                            {status === 'COMPLETED' ? (
                              <div className="flex items-center gap-1.5">
                                <Badge tone={score >= 60 ? 'red' : score >= 20 ? 'amber' : 'green'}>
                                  {tier || (score >= 60 ? 'HIGH_RISK' : score >= 20 ? 'SENSITIVE' : 'SAFE')} ({score ?? 0})
                                </Badge>
                              </div>
                            ) : status === 'FAILED' ? (
                              <Badge tone="red">FAILED</Badge>
                            ) : (
                              <Badge tone="neutral">PENDING</Badge>
                            )}
                          </td>
                          <td>
                            <Badge tone="purple">{file.source || 'google_drive'}</Badge>
                          </td>
                          <td className="whitespace-nowrap text-slate-600 dark:text-slate-400">
                            {file.modified_time ? formatDateTime(file.modified_time) : '—'}
                          </td>
                          <td className="text-slate-600 dark:text-slate-400">
                            {file.size == null ? '—' : `${(file.size / 1024).toFixed(1)} KB`}
                          </td>
                          <td className="text-right">
                            <div className="flex justify-end gap-2">
                              <button type="button" className={btnSecondary} onClick={() => openFile(file)}>
                                Details
                              </button>
                              {['ADMIN', 'USER'].includes(user?.role) ? (
                                <button
                                  type="button"
                                  className={btnSecondary}
                                  onClick={async () => {
                                    setDownloadError('');
                                    try {
                                      await downloadDriveFile(file.file_id);
                                    } catch (err) {
                                      setDownloadError(errorMessage(err, 'Download failed.'));
                                    }
                                  }}
                                  title="Download"
                                >
                                  <Download size={14} />
                                </button>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {user?.role === 'VISITOR' ? (
              <p className="border-t border-slate-800 p-3 text-xs text-slate-400">
                Visitor access is read-only. File downloads are disabled for your role.
              </p>
            ) : null}
            {downloadError ? (
              <p role="alert" className="border-t border-red-900/50 p-3 text-xs text-red-300">
                {downloadError}
              </p>
            ) : null}
          </Panel>
        </div>
      ) : (
        <Panel
          title="PII findings"
          subtitle="Derived metadata only. Raw text and matched values are not stored."
          actions={
            <select
              value={findingCategory}
              onChange={(event) => setFindingCategory(event.target.value)}
              className={`${selectClass} w-44`}
            >
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
            <EmptyState
              icon={ShieldCheck}
              title="No PII findings"
              message="Findings appear after cloud content or a user-selected image/PDF is scanned. No synthetic findings are displayed."
            />
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
                      <td className="whitespace-nowrap text-slate-400" title={formatDateTime(finding.timestamp)}>
                        {timeAgo(finding.timestamp)}
                      </td>
                      <td>
                        <Badge tone={CATEGORY_TONE[finding.category] || 'neutral'}>{finding.category}</Badge>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-slate-200">
                            {formatScore(finding.sensitivity_score, 0)}
                          </span>
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                            <div
                              className={`h-full ${
                                finding.sensitivity_score >= 60
                                  ? 'bg-red-500'
                                  : finding.sensitivity_score >= 20
                                  ? 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${Math.min(100, Number(finding.sensitivity_score) || 0)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="max-w-[18rem] text-[11px] text-slate-400">
                        {(finding.entities || []).length === 0
                          ? 'None retained'
                          : finding.entities.map((entity) => `${entity.entity_type} ×${entity.count}`).join(', ')}
                      </td>
                      <td className="text-slate-400">{finding.user_id}</td>
                      <td className="max-w-[12rem] truncate text-[11px] text-slate-500" title={finding.file_id || finding.event_id || ''}>
                        {finding.file_id || finding.event_id || '—'}
                      </td>
                      <td>
                        <Badge
                          tone={
                            finding.source === 'offline_cloud_analysis'
                              ? 'purple'
                              : finding.source === 'ocr_upload'
                              ? 'purple'
                              : 'blue'
                          }
                        >
                          {finding.source === 'offline_cloud_analysis'
                            ? 'Offline cloud'
                            : finding.source === 'ocr_upload'
                            ? 'OCR upload'
                            : 'Text sample'}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={finding.engine === 'presidio' ? 'green' : 'amber'}>{finding.engine}</Badge>
                      </td>
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
          ? 'Offline analysis inspects cloud document files in memory (.txt, .docx, .xlsx, .pdf, OCR images). The original content and raw extracted text are immediately discarded after Presidio scoring.'
          : 'Install the optional OCR Python packages and Tesseract executable to enable image and scanned-PDF scans. Existing metadata and text analysis remain available.'}
      </InlineNotice>

      {/* File Detail Drawer with Similar Files */}
      <Drawer
        open={Boolean(selectedFile)}
        onClose={() => setSelectedFile(null)}
        title={selectedFile?.name || 'File details'}
        subtitle={selectedFile?.file_id}
      >
        {selectedFile ? (
          <div className="space-y-5">
            <section className="grid grid-cols-2 gap-3">
              <KeyValue label="Owner">{selectedFile.owner_email || '—'}</KeyValue>
              <KeyValue label="MIME type">{selectedFile.mime_type || '—'}</KeyValue>
              <KeyValue label="Source">{selectedFile.source || 'google_drive'}</KeyValue>
              <KeyValue label="Created">{selectedFile.created_time ? formatDateTime(selectedFile.created_time) : '—'}</KeyValue>
              <KeyValue label="Modified">{selectedFile.modified_time ? formatDateTime(selectedFile.modified_time) : '—'}</KeyValue>
              <KeyValue label="Analysis status">
                <Badge tone={selectedFile.analysis_status === 'COMPLETED' ? 'green' : selectedFile.analysis_status === 'FAILED' ? 'red' : 'neutral'}>
                  {selectedFile.analysis_status || 'PENDING'}
                </Badge>
              </KeyValue>
              <KeyValue label="Sensitivity">
                {selectedFile.sensitivity_score != null
                  ? `${selectedFile.sensitivity_score}/100 (${selectedFile.sensitivity_tier || 'SAFE'})`
                  : 'Not analyzed'}
              </KeyValue>
              <KeyValue label="Sharing scope">{selectedFile.sharing_scope || 'private'}</KeyValue>
              <KeyValue label="Last analyzed">
                {selectedFile.last_analyzed_at ? formatDateTime(selectedFile.last_analyzed_at) : 'Never'}
              </KeyValue>
            </section>

            {selectedFile.analysis_error ? (
              <InlineNotice tone="error">
                <strong>Analysis error:</strong> {selectedFile.analysis_error}
              </InlineNotice>
            ) : null}

            {/* Vector Similarity Matching (Base Paper Phase 1) */}
            <section className="border-t border-slate-200 dark:border-slate-800 pt-4">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                  <Sparkles size={14} className="text-blue-500" />
                  Similar cloud files (Vector Index)
                </h3>
                <span className="text-[10px] text-slate-500">Cosine similarity on safe metadata</span>
              </div>
              {similarLoading ? (
                <LoadingState label="Computing vector similarities…" />
              ) : similarFiles.length === 0 ? (
                <p className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-500">
                  No similar files indexed in the vector store yet. Run offline analysis to index cloud documents.
                </p>
              ) : (
                <div className="space-y-2">
                  {similarFiles.map((sim) => (
                    <div
                      key={sim.file_id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 p-2.5 transition hover:bg-slate-100 dark:hover:bg-slate-800/40"
                    >
                      <div className="min-w-0 pr-2">
                        <p className="truncate text-xs font-semibold text-slate-900 dark:text-slate-100">{sim.name}</p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <Badge tone={CATEGORY_TONE[sim.sensitivity_tier] || 'neutral'}>{sim.sensitivity_tier || 'SAFE'}</Badge>
                          <span className="text-[10px] text-slate-500">{Math.round((sim.similarity || 0) * 100)}% similarity</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        className={btnSecondary}
                        onClick={() => {
                          const matched = files.find((f) => f.file_id === sim.file_id);
                          if (matched) openFile(matched);
                        }}
                      >
                        View
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Derived findings */}
            <section className="border-t border-slate-200 dark:border-slate-800 pt-4">
              <h3 className="mb-2 text-sm font-bold text-slate-900 dark:text-slate-100">Derived findings ({fileFindings.length})</h3>
              {fileLoading ? (
                <LoadingState label="Loading file findings…" />
              ) : fileError ? (
                <ErrorState message={fileError} onRetry={() => openFile(selectedFile)} />
              ) : fileFindings.length === 0 ? (
                <p className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 p-3 text-xs text-slate-500">
                  No PII findings are linked to this file. That does not mean the file is safe; content may not have been analysed yet.
                </p>
              ) : (
                <div className="space-y-2">
                  {fileFindings.map((finding) => (
                    <div key={finding.finding_id} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/40 p-3">
                      <div className="flex items-center justify-between">
                        <Badge tone={CATEGORY_TONE[finding.category] || 'neutral'}>{finding.category}</Badge>
                        <span className="font-mono text-xs text-slate-900 dark:text-slate-200">{finding.sensitivity_score}/100</span>
                      </div>
                      <p className="mt-1.5 text-[11px] text-slate-600 dark:text-slate-400">
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
                onClick={() => {
                  setScanMode(mode);
                  setAnalyzeError('');
                  setOcrResult(null);
                  setAnalyzeResult(null);
                }}
                className={`flex-1 rounded-md px-3 py-2 text-xs font-semibold transition ${
                  scanMode === mode ? 'bg-blue-500/15 text-blue-200' : 'text-slate-500 hover:text-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {scanMode === 'text' ? (
            <div>
              <label htmlFor="analyze-text" className={labelClass}>
                Sample text to check for PII
              </label>
              <textarea
                id="analyze-text"
                rows={6}
                value={analyzeValue}
                onChange={(event) => setAnalyzeValue(event.target.value)}
                placeholder="Paste a non-sensitive snippet to test the PII classifier..."
                className="w-full rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-200 placeholder-slate-600 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          ) : (
            <div>
              <label htmlFor="ocr-upload" className={labelClass}>
                Select an image or scanned PDF
              </label>
              <input
                id="ocr-upload"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp"
                onChange={(event) => setOcrFile(event.target.files?.[0] || null)}
                className="w-full rounded-lg border border-slate-800 bg-slate-900/60 p-2 text-xs text-slate-200 file:mr-3 file:rounded-md file:border-0 file:bg-blue-500/15 file:px-3 file:py-1 file:text-xs file:font-semibold file:text-blue-200 hover:file:bg-blue-500/25"
              />
              <p className="mt-1 text-[11px] text-slate-500">
                Supported: PDF (up to 10 pages), PNG, JPEG, TIFF, BMP, WebP up to 10 MB.
              </p>
            </div>
          )}

          {analyzeError ? <p className="text-xs text-red-400">{analyzeError}</p> : null}

          <div className="flex justify-end gap-2">
            <button type="button" className={btnSecondary} onClick={closeAnalyze}>
              Cancel
            </button>
            <button
              type="submit"
              className={btnPrimary}
              disabled={scanMode === 'ocr' ? ocrBusy || !ocrFile : analyzeBusy || !analyzeValue.trim()}
            >
              {(scanMode === 'ocr' ? ocrBusy : analyzeBusy) ? (
                <>
                  <Loader2 size={13} className="animate-spin" />
                  Scanning…
                </>
              ) : (
                'Run check'
              )}
            </button>
          </div>
        </form>

        {analyzeResult ? (
          <div className="mt-5 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">Scan result</span>
              <Badge tone={CATEGORY_TONE[analyzeResult.category] || 'neutral'}>{analyzeResult.category}</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Sensitivity score: <span className="font-mono text-slate-200">{analyzeResult.sensitivity_score}/100</span>
            </p>
            <div className="mt-2 text-[11px] text-slate-400">
              Entities found:{' '}
              {(analyzeResult.entities || []).length === 0
                ? 'None'
                : analyzeResult.entities.map((e) => `${e.entity_type} ×${e.count}`).join(', ')}
            </div>
          </div>
        ) : null}

        {ocrResult ? (
          <div className="mt-5 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">OCR scan result</span>
              <Badge tone={CATEGORY_TONE[ocrResult.category] || 'neutral'}>{ocrResult.category}</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Sensitivity score: <span className="font-mono text-slate-200">{ocrResult.sensitivity_score}/100</span>
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Engine: {ocrResult.ocr_engine || 'tesseract'} · Pages: {ocrResult.page_count ?? 1}
            </p>
            <div className="mt-2 text-[11px] text-slate-400">
              Entities found:{' '}
              {(ocrResult.entities || []).length === 0
                ? 'None'
                : ocrResult.entities.map((e) => `${e.entity_type} ×${e.count}`).join(', ')}
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
