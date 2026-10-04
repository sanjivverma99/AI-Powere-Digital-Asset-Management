import { useState, useEffect } from 'react'
import './App.css'

const API_BASE_URL = 'http://127.0.0.1:8000'

const FILTERS = [
  { value: 'all', label: 'All assets' },
  { value: 'image', label: 'Images' },
  { value: 'video', label: 'Videos' },
  { value: 'pdf', label: 'PDFs' },
]

const QUICK_SUGGESTIONS = [
  'A woman standing with a cat',
  'Customer testimonial videos',
  'Videos containing construction activity',
  'Images showing a modern living room',
  'Brochures related to residential projects',
  'Yellow flower',
  'Mountain landscape',
  'Document with text',
]

function NexusLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="nexus-logo-icon">
      <path d="M12 2L2 7l10 5 10-5-10-5z" fill="url(#nexus-grad)" stroke="none" />
      <path d="M2 17l10 5 10-5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 12l10 5 10-5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <defs>
        <linearGradient id="nexus-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
          <stop stopColor="#a855f7" />
          <stop offset="1" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
    </svg>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 5 5" />
    </svg>
  )
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m12 2 1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7L12 2Z" />
      <path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 6.5A2.5 2.5 0 0 1 5.5 4H10l2 2h6.5A2.5 2.5 0 0 1 21 8.5v8A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5v-10Z" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="4" width="6" height="6" rx="1" />
      <rect x="4" y="14" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  )
}

function ImageIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <circle cx="9" cy="9" r="1.5" />
      <path d="m5.5 17 4.5-4 3.2 2.7 2.2-2 3.1 3.3" />
    </svg>
  )
}

function VideoIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="6" width="13" height="12" rx="2" />
      <path d="m16 10 5-3v10l-5-3" />
    </svg>
  )
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3h8l4 4v14H6z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </svg>
  )
}

function DatabaseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="7" ry="3" />
      <path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
      <path d="M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7 7 10 10M17 7 7 17" />
    </svg>
  )
}

function ExternalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 5h5v5M19 5l-8 8" />
      <path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </svg>
  )
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return null
  const totalSeconds = Math.round(seconds)
  if (totalSeconds < 60) return `${totalSeconds}s`
  const minutes = Math.floor(totalSeconds / 60)
  const remainingSeconds = totalSeconds % 60
  return `${minutes}m ${remainingSeconds}s`
}

function getFileTypeLabel(fileType) {
  switch (fileType) {
    case 'image': return 'Image'
    case 'video': return 'Video'
    case 'pdf': return 'PDF Document'
    default: return fileType || 'Asset'
  }
}

function getFileTypeIcon(fileType) {
  switch (fileType) {
    case 'image': return <ImageIcon />
    case 'video': return <VideoIcon />
    case 'pdf': return <FileIcon />
    default: return <FileIcon />
  }
}

export default function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('nexus_dam_theme') || 'dark'
  })

  const [query, setQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [error, setError] = useState('')
  const [selectedAsset, setSelectedAsset] = useState(null)
  const [aiStatus, setAiStatus] = useState({
    status: 'checking',
    detail: 'Checking AI service availability...',
  })

  const [indexing, setIndexing] = useState(false)
  const [indexJob, setIndexJob] = useState(null)
  const [showIndexProgress, setShowIndexProgress] = useState(false)
  const [indexMessage, setIndexMessage] = useState('')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('nexus_dam_theme', theme)
  }, [theme])

  useEffect(() => {
    let active = true

    async function refreshAiStatus() {
      try {
        const response = await fetch(`${API_BASE_URL}/health/ai`)
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Unable to check AI service availability.')
        }
        if (active) setAiStatus(data)
      } catch (statusError) {
        if (active) {
          setAiStatus({
            status: 'offline',
            detail: statusError.message || 'Unable to reach the DAM backend.',
          })
        }
      }
    }

    refreshAiStatus()
    const intervalId = window.setInterval(refreshAiStatus, 15000)
    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [])

  const aiStatusLabel = {
    checking: 'Checking AI...',
    ready: 'Neural Engine Ready',
    degraded: 'AI Models Missing',
    offline: 'Ollama Offline',
  }[aiStatus.status] || 'AI Status Unknown'

  function toggleTheme() {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  async function searchAssets(searchValue = query) {
    const trimmedQuery = searchValue.trim()

    if (!trimmedQuery) {
      setError('Enter a natural-language description to search.')
      return
    }

    setSearching(true)
    setError('')
    setHasSearched(true)

    try {
      const params = new URLSearchParams({
        q: trimmedQuery,
        limit: '30',
      })

      if (activeFilter !== 'all') {
        params.set('file_type', activeFilter)
      }

      const response = await fetch(`${API_BASE_URL}/search?${params.toString()}`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Search failed.')
      }

      setResults(data.results || [])
    } catch (searchError) {
      setResults([])
      setError(searchError.message || 'Unable to connect to the DAM backend.')
    } finally {
      setSearching(false)
    }
  }

  function handleSearchSubmit(event) {
    event.preventDefault()
    searchAssets()
  }

  function clearSearch() {
    setQuery('')
    setResults([])
    setHasSearched(false)
    setError('')
  }

  async function startIndexing(force = false) {
    if (indexing) return

    setIndexing(true)
    setShowIndexProgress(true)
    setIndexMessage('Scanning local library...')
    setError('')

    try {
      const scanResponse = await fetch(`${API_BASE_URL}/index/scan`, { method: 'POST' })
      const scanData = await scanResponse.json()

      if (!scanResponse.ok) {
        throw new Error(scanData.detail || 'Library scan failed.')
      }

      setIndexMessage(`Scan complete — ${scanData.total_files} supported files found.`)

      const startResponse = await fetch(
        `${API_BASE_URL}/index/start${force ? '?force=true' : ''}`,
        { method: 'POST' }
      )
      const startData = await startResponse.json()

      if (!startResponse.ok) {
        throw new Error(startData.detail || 'Unable to start indexing.')
      }

      if (startData.total_files === 0) {
        setIndexJob({
          total_files: 0,
          processed_files: 0,
          successful_files: 0,
          failed_files: 0,
          skipped_files: 0,
          status: 'completed',
          progress_percent: 100,
        })
        setIndexMessage('Your library is already fully indexed.')
        return
      }

      const jobId = startData.job_id
      setIndexJob({
        total_files: startData.total_files,
        processed_files: 0,
        successful_files: 0,
        failed_files: 0,
        skipped_files: 0,
        status: 'running',
        progress_percent: 0,
      })

      setIndexMessage(`Indexing ${startData.total_files} files with neural embeddings...`)

      while (true) {
        const jobResponse = await fetch(`${API_BASE_URL}/index/jobs/${jobId}`)
        const jobData = await jobResponse.json()

        if (!jobResponse.ok) {
          throw new Error(jobData.detail || 'Unable to read indexing progress.')
        }

        setIndexJob(jobData)

        if (jobData.status === 'completed' || jobData.status === 'failed') {
          break
        }

        await new Promise((resolve) => window.setTimeout(resolve, 1000))
      }

      const latestJob = await fetch(`${API_BASE_URL}/index/jobs/${jobId}`).then((r) => r.json())

      if (latestJob.status === 'completed') {
        setIndexMessage(
          `Indexing complete — ${latestJob.successful_files} processed, ${latestJob.failed_files} failed, ${latestJob.skipped_files} skipped.`
        )
      } else {
        setIndexMessage(`Indexing stopped with status: ${latestJob.status}.`)
      }

      if (query.trim()) {
        await searchAssets(query)
      }
    } catch (indexError) {
      setIndexMessage(`Indexing error: ${indexError.message}`)
    } finally {
      setIndexing(false)
    }
  }

  function renderAssetPreview(asset) {
    if (!asset) return null
    const fileUrl = `${API_BASE_URL}/assets/${asset.asset_id}/file`

    if (asset.file_type === 'image') {
      return <img src={fileUrl} alt={asset.filename} className="preview-image" />
    }

    if (asset.file_type === 'video') {
      return (
        <video
          src={fileUrl}
          controls
          autoPlay
          className="preview-video"
        />
      )
    }

    if (asset.file_type === 'pdf') {
      return (
        <iframe
          src={fileUrl}
          title={asset.filename}
          className="preview-pdf"
        />
      )
    }

    return (
      <div className="preview-fallback">
        <div className="preview-fallback-icon">{getFileTypeIcon(asset.file_type)}</div>
        <p>Preview is not available for this file type.</p>
      </div>
    )
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <NexusLogo />
          </div>
          <div>
            <div className="brand-name">
              <span>Nexus</span>DAM
            </div>
            <div className="brand-subtitle">Neural Media & Retrieval Engine</div>
          </div>
        </div>

        <div className="topbar-actions">
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Studio Light Theme' : 'Switch to Cyber Dark Theme'}
            aria-label="Toggle visual theme"
          >
            {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            <span>{theme === 'dark' ? 'Light mode' : 'Cyber dark'}</span>
          </button>

          <div
            className={`local-status local-status-${aiStatus.status}`}
            title={aiStatus.detail}
            aria-live="polite"
          >
            <span className="status-dot" />
            <span>{aiStatusLabel}</span>
          </div>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <div className="sidebar-section">
            <p className="sidebar-label">Navigation</p>

            <button type="button" className="sidebar-item active">
              <GridIcon />
              <span>Asset Library</span>
            </button>

            <button
              type="button"
              className="sidebar-item"
              onClick={startIndexing}
              disabled={indexing}
            >
              <DatabaseIcon />
              <span>{indexing ? 'Indexing library...' : 'Index Library'}</span>
            </button>
          </div>

          <div className="sidebar-section">
            <p className="sidebar-label">Filter by type</p>

            {FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`sidebar-item ${activeFilter === filter.value ? 'selected' : ''}`}
                onClick={() => {
                  setActiveFilter(filter.value)
                  if (query.trim()) {
                    setTimeout(() => searchAssets(query), 0)
                  }
                }}
              >
                {filter.value === 'all' ? (
                  <GridIcon />
                ) : filter.value === 'image' ? (
                  <ImageIcon />
                ) : filter.value === 'video' ? (
                  <VideoIcon />
                ) : (
                  <FileIcon />
                )}
                <span>{filter.label}</span>
              </button>
            ))}
          </div>

          <div className="sidebar-bottom">
            <div className="library-card">
              <FolderIcon />
              <div>
                <strong>Local-First Storage</strong>
                <span>Postgres & Qdrant run securely on this device.</span>
              </div>
            </div>
          </div>
        </aside>

        <main className="main-content">
          <section className="hero-section">
            <div className="hero-glow-blob" />
            <div className="hero-text-wrap">
              <div className="cyber-badge">
                <SparkIcon />
                <span>AI-POWERED NEURAL RETRIEVAL</span>
              </div>

              <h1>
                Find the right <span className="highlight-text">asset</span> with a simple description.
              </h1>

              <p className="hero-copy">
                Semantic neural search across images, videos, and PDF documents. Results are dynamically ranked by vector cosine relevance.
              </p>
            </div>

            <button
              type="button"
              className="index-button"
              onClick={() => startIndexing(true)}
              disabled={indexing}
            >
              <DatabaseIcon />
              {indexing ? 'Indexing library in background...' : 'Re-index Local Library'}
            </button>
          </section>

          <form className="search-panel" onSubmit={handleSearchSubmit}>
            <div className="search-icon">
              <SearchIcon />
            </div>

            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='Try "A woman standing with a cat", "construction activity", or "modern living room"...'
              aria-label="Natural language search"
            />

            {query && (
              <button
                type="button"
                className="clear-search-button"
                onClick={clearSearch}
                aria-label="Clear query"
                title="Clear"
              >
                <CloseIcon />
              </button>
            )}

            <button type="submit" className="search-button" disabled={searching}>
              {searching ? 'Searching...' : 'Search'}
            </button>
          </form>

          {/* Quick Suggestion Pills */}
          <div className="quick-suggestions-wrap">
            <span className="suggestions-label">Try searching:</span>
            <div className="suggestion-pills">
              {QUICK_SUGGESTIONS.map((item) => (
                <button
                  key={item}
                  type="button"
                  className="quick-pill"
                  onClick={() => {
                    setQuery(item)
                    searchAssets(item)
                  }}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          {indexJob && showIndexProgress && (
            <section className="index-progress">
              <button
                type="button"
                className="progress-close"
                onClick={() => setShowIndexProgress(false)}
                aria-label="Close"
              >
                <CloseIcon />
              </button>

              <div className="progress-header">
                <div>
                  <span className="progress-title">Neural Library Indexing</span>
                  <span className="progress-detail">
                    {indexJob.processed_files} / {indexJob.total_files} assets processed
                  </span>
                </div>
                <strong>{indexJob.progress_percent}%</strong>
              </div>

              <div className="progress-track">
                <div
                  className="progress-fill"
                  style={{ width: `${Math.min(100, indexJob.progress_percent)}%` }}
                />
              </div>

              <div className="progress-stats">
                <span><b>{indexJob.successful_files}</b> successful</span>
                <span><b>{indexJob.skipped_files}</b> skipped</span>
                <span><b>{indexJob.failed_files}</b> failed</span>
                <span className="progress-status">{indexJob.status}</span>
              </div>
            </section>
          )}

          {indexMessage && !indexing && (
            <div className="info-message">{indexMessage}</div>
          )}

          {error && <div className="error-message">{error}</div>}

          <section className="results-section">
            <div className="results-header">
              <div>
                <p className="eyebrow">RETRIEVAL RESULTS</p>
                <h2>
                  {searching
                    ? 'Computing neural rankings…'
                    : hasSearched
                    ? `${results.length} relevant assets found`
                    : 'Indexed Asset Collection'}
                </h2>
              </div>

              {hasSearched && (
                <div className="result-context">
                  <span className="filter-pill">
                    {activeFilter === 'all' ? 'All Formats' : getFileTypeLabel(activeFilter)}
                  </span>
                  <span>•</span>
                  <span>Ranked by Semantic Relevance</span>
                </div>
              )}
            </div>

            {!hasSearched ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <SparkIcon />
                </div>
                <h3>Natural-Language Search</h3>
                <p>
                  NexusDAM indexes the actual visual scenes, spoken content, and text within your local images, videos, and PDFs.
                </p>
              </div>
            ) : results.length === 0 && !searching ? (
              <div className="empty-state">
                <div className="empty-icon">
                  <SearchIcon />
                </div>
                <h3>No matching assets found</h3>
                <p>Try a different natural-language description or clear your media filter.</p>
              </div>
            ) : (
              <div className="results-grid">
                {results.map((asset) => {
                  const fileUrl = `${API_BASE_URL}/assets/${asset.asset_id}/file`
                  const score = Number(asset.score || 0)
                  const scorePercent = Math.min(100, Math.round(score * 100))

                  return (
                    <article
                      key={asset.asset_id}
                      className="asset-card"
                      onClick={() => setSelectedAsset(asset)}
                    >
                      <div className="asset-thumbnail">
                        {asset.file_type === 'image' ? (
                          <img src={fileUrl} alt={asset.filename} loading="lazy" />
                        ) : asset.file_type === 'video' ? (
                          <div className="video-card-thumb">
                            <video src={fileUrl} muted preload="metadata" />
                            <div className="play-overlay">
                              <VideoIcon />
                            </div>
                          </div>
                        ) : (
                          <div className="pdf-card-thumb">
                            <FileIcon />
                            <span>PDF Document</span>
                          </div>
                        )}

                        <span className={`type-badge badge-${asset.file_type}`}>
                          {asset.file_type.toUpperCase()}
                        </span>

                        {score > 0 && (
                          <span className="score-badge" title={`Vector cosine score: ${score.toFixed(4)}`}>
                            {scorePercent}% match
                          </span>
                        )}
                      </div>

                      <div className="asset-info">
                        <h4 className="asset-title" title={asset.filename}>
                          {asset.filename}
                        </h4>

                        <p className="asset-description">
                          {asset.description || 'Processed and indexed asset.'}
                        </p>

                        <div className="asset-meta">
                          <span>{formatBytes(asset.size_bytes)}</span>
                          {asset.width && asset.height && (
                            <span>• {asset.width}×{asset.height}</span>
                          )}
                          {asset.duration_seconds && (
                            <span>• {formatDuration(asset.duration_seconds)}</span>
                          )}
                          {asset.page_count && (
                            <span>• {asset.page_count} pg</span>
                          )}
                        </div>
                      </div>
                    </article>
                  )
                })}
              </div>
            )}
          </section>
        </main>
      </div>

      {/* Asset Preview Modal */}
      {selectedAsset && (
        <div className="modal-backdrop" onClick={() => setSelectedAsset(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="modal-close"
              onClick={() => setSelectedAsset(null)}
              aria-label="Close preview"
            >
              <CloseIcon />
            </button>

            <div className="modal-body">
              <div className="modal-preview-pane">
                {renderAssetPreview(selectedAsset)}
              </div>

              <div className="modal-details-pane">
                <div className="modal-type-header">
                  <span className={`type-badge badge-${selectedAsset.file_type}`}>
                    {selectedAsset.file_type.toUpperCase()}
                  </span>
                  {selectedAsset.score > 0 && (
                    <span className="score-badge">
                      Score: {Number(selectedAsset.score).toFixed(4)}
                    </span>
                  )}
                </div>

                <h3 className="modal-asset-title">{selectedAsset.filename}</h3>

                <div className="modal-detail-block">
                  <p className="detail-label">AI Content Understanding</p>
                  <p className="detail-value">{selectedAsset.description || 'No description available.'}</p>
                </div>

                <div className="modal-meta-grid">
                  <div>
                    <span className="meta-key">File Size</span>
                    <span className="meta-val">{formatBytes(selectedAsset.size_bytes)}</span>
                  </div>
                  <div>
                    <span className="meta-key">MIME Type</span>
                    <span className="meta-val">{selectedAsset.mime_type || '—'}</span>
                  </div>
                  {selectedAsset.width && selectedAsset.height && (
                    <div>
                      <span className="meta-key">Resolution</span>
                      <span className="meta-val">{selectedAsset.width} × {selectedAsset.height} px</span>
                    </div>
                  )}
                  {selectedAsset.duration_seconds && (
                    <div>
                      <span className="meta-key">Duration</span>
                      <span className="meta-val">{formatDuration(selectedAsset.duration_seconds)}</span>
                    </div>
                  )}
                  {selectedAsset.page_count && (
                    <div>
                      <span className="meta-key">Page Count</span>
                      <span className="meta-val">{selectedAsset.page_count} pages</span>
                    </div>
                  )}
                </div>

                <div className="modal-action-row">
                  <a
                    href={`${API_BASE_URL}/assets/${selectedAsset.asset_id}/file`}
                    target="_blank"
                    rel="noreferrer"
                    className="modal-primary-btn"
                  >
                    <ExternalIcon />
                    <span>Open Original Media</span>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}