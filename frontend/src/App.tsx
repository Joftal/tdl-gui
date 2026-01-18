import { useState, useEffect, useRef } from 'react';
import './App.css';
import { GetVersion, Download, Upload, SelectFile, SelectFolder, SetProxy, GetProxy, SetTDLPath, GetTDLPath, SelectTDLFile, SetNamespace, GetNamespace, SetDownloadPath, GetDownloadPath, SelectDownloadDir, SelectTextFile, ReadTextFile, SelectFolderByFile, SaveWindowSize, OpenDownloadDir } from "../wailsjs/go/main/App";
import { EventsOn } from "../wailsjs/runtime/runtime";

// Types
interface LogEntry {
    id: number;
    text: string;
    type: 'normal' | 'progress';
}

// Icons
const IconDownload = () => <svg viewBox="0 0 24 24" width="18" height="18"><path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z" /></svg>;
const IconUpload = () => <svg viewBox="0 0 24 24" width="18" height="18"><path d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z" /></svg>;
const IconSettings = () => <svg viewBox="0 0 24 24" width="18" height="18"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84a.484.484 0 0 0-.48.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.488.488 0 0 0-.59.22L2.74 8.87a.49.49 0 0 0 .12.61l2.03 1.58c-.05.3-.07.63-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.48-.41l.36-2.54c.59-.24 1.13-.58 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32a.49.49 0 0 0-.12-.61l-2.03-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" /></svg>;
const IconFolder = () => <svg viewBox="0 0 24 24" width="18" height="18"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z" /></svg>;
const IconTDL = () => <div style={{ fontWeight: '900', fontSize: '16px' }}>TDL</div>;

function App() {
    const [version, setVersion] = useState("Loading...");
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [activeTab, setActiveTab] = useState("download");
    const [status, setStatus] = useState("就绪");
    const [isDownloading, setIsDownloading] = useState(false);

    // Settings
    const [proxy, setProxy] = useState("");
    const [tdlPath, setTdlPath] = useState("");
    const [namespace, setNamespace] = useState("");
    const [downloadPath, setDownloadPath] = useState("");

    // Forms
    const [dlUrl, setDlUrl] = useState("");
    const [dlThreads, setDlThreads] = useState(8);
    const [upPath, setUpPath] = useState("");
    const [upChat, setUpChat] = useState("");
    const [upToSaved, setUpToSaved] = useState(false);
    const [upThreads, setUpThreads] = useState(8);
    const [upRemove, setUpRemove] = useState(false);
    const [upAsPhoto, setUpAsPhoto] = useState(false);

    // Batch Download Queue
    const [taskQueue, setTaskQueue] = useState<string[]>([]);
    const [totalTasks, setTotalTasks] = useState(0);

    const logEndRef = useRef<HTMLDivElement>(null);
    const logIdCounter = useRef(0);

    // Check queue refs for event listeners (stale closure fix)
    const queueRef = useRef<string[]>([]);
    const processingRef = useRef(false);

    const createLog = (text: string, type: 'normal' | 'progress'): LogEntry => ({
        id: logIdCounter.current++,
        text,
        type
    });

    useEffect(() => {
        // Sync ref with state
        queueRef.current = taskQueue;
    }, [taskQueue]);

    // Window Resize Listener
    useEffect(() => {
        let timeoutId: number;

        const handleResize = () => {
            clearTimeout(timeoutId);
            timeoutId = window.setTimeout(async () => {
                const w = window.outerWidth;
                const h = window.outerHeight;
                try {
                    await SaveWindowSize(w, h);
                } catch (e) { }
            }, 1000);
        };

        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
            clearTimeout(timeoutId);
        }
    }, []);

    useEffect(() => {
        refreshVersion();
        GetProxy().then(setProxy).catch(() => { });
        GetTDLPath().then(setTdlPath).catch(() => { });
        GetNamespace().then(setNamespace).catch(() => { });
        GetDownloadPath().then(setDownloadPath).catch(() => { });

        const unOffLog = EventsOn("tdl:log", (data: string) => {
            let type: 'normal' | 'progress' = 'normal';
            let cleanData = data;

            if (data.startsWith("PROG:")) {
                type = 'progress';
                cleanData = data.substring(5);
            } else if (data.startsWith("LOG:")) {
                type = 'normal';
                cleanData = data.substring(4);
            }

            setLogs(prev => {
                if (prev.length === 0) return [createLog(cleanData, type)];
                const lastLog = prev[prev.length - 1];

                if (type === 'progress' && lastLog.type === 'progress') {
                    const newLogs = [...prev];
                    newLogs[newLogs.length - 1] = { ...lastLog, text: cleanData };
                    return newLogs;
                }

                const newEntry = createLog(cleanData, type);
                if (prev.length > 500) {
                    return [...prev.slice(-400), newEntry];
                }
                return [...prev, newEntry];
            });
        });

        // Handler for task completion (success or error)
        const handleTaskCompletion = (msg: string, isSuccess: boolean) => {
            setLogs(prev => [...prev, createLog((isSuccess ? "✅ " : "❌ ") + msg, 'normal')]);

            // Check if we have more tasks in queue
            if (queueRef.current.length > 0) {
                const nextUrl = queueRef.current[0];
                const remaining = queueRef.current.slice(1);

                // Update State
                setTaskQueue(remaining);
                setStatus(`准备下载下一个任务 (剩余 ${remaining.length})...`);
                setDlUrl(nextUrl); // Visual update

                // Delay slightly to allow UI to breathe
                setTimeout(() => {
                    setLogs(prev => [...prev, createLog(`🚀 自动开始下一个任务: ${nextUrl}`, 'normal')]);
                    Download(nextUrl, dlThreads); // Re-use current thread setting (careful with closure here, but dlThreads usually static during batch)
                }, 1000);
            } else {
                // All done
                setStatus("所有任务已完成");
                setIsDownloading(false);
                processingRef.current = false;
                setTotalTasks(0);
            }
        };

        const unOffSuccess = EventsOn("tdl:success", (data: string) => {
            handleTaskCompletion(data, true);
        });

        const unOffError = EventsOn("tdl:error", (data: string) => {
            handleTaskCompletion(data, false);
        });

        return () => {
            unOffLog();
            unOffSuccess();
            unOffError();
        };
    }, []); // Empty dependency array: simplistic approach. Note: dlThreads inside closure might be stale if changed during batch.

    // Auto-scroll
    useEffect(() => {
        if (logEndRef.current) {
            logEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    const refreshVersion = () => {
        setVersion("Loading...");
        GetVersion().then(setVersion).catch(() => setVersion("Unknown"));
    }

    const handleDownload = () => {
        if (!dlUrl) return;
        setStatus("任务启动中...");
        setIsDownloading(true);
        processingRef.current = true;
        Download(dlUrl, dlThreads);
    };

    const handleBatchImport = async () => {
        if (isDownloading) return;
        try {
            const filePath = await SelectTextFile();
            if (!filePath) return;

            const content = await ReadTextFile(filePath);
            const rawUrls = content.split(/\r?\n/).map(line => line.trim()).filter(line => line.length > 0);

            // Remove duplicates
            const uniqueUrls = Array.from(new Set(rawUrls));
            const urls = uniqueUrls;
            const removedCount = rawUrls.length - uniqueUrls.length;

            if (urls.length === 0) {
                setStatus("文件为空或无效");
                return;
            }

            const firstUrl = urls[0];
            const remaining = urls.slice(1);

            setDlUrl(firstUrl);
            setTaskQueue(remaining);
            setTotalTasks(urls.length);

            let logMsg = `📂 已导入批量任务: 共 ${urls.length} 个链接`;
            if (removedCount > 0) {
                logMsg += ` (已自动过滤 ${removedCount} 个重复项)`;
            }

            setLogs(prev => [...prev, createLog(logMsg, 'normal')]);
            setStatus(`已加载 ${urls.length} 个任务，点击“开始下载”启动`);

        } catch (e) {
            setStatus("读取文件失败");
        }
    }

    const handleUpload = () => {
        if (!upPath || (!upToSaved && !upChat)) return;
        setStatus("任务启动中...");
        setIsDownloading(true);
        // If upToSaved is true, pass empty string for chat
        Upload(upPath, upToSaved ? "" : upChat, upThreads, upRemove, upAsPhoto);
    };

    const pickFile = async () => {
        const file = await SelectFile();
        if (file) setUpPath(file);
    };

    const pickFolder = async () => {
        const folder = await SelectFolder();
        if (folder) setUpPath(folder);
    };

    const pickFolderByFile = async () => {
        const folder = await SelectFolderByFile();
        if (folder) setUpPath(folder);
    }

    const pickTDLFile = async () => {
        const file = await SelectTDLFile();
        if (file) {
            setTdlPath(file);
            SetTDLPath(file);
            refreshVersion();
        }
    }

    const pickDownloadDir = async () => {
        const dir = await SelectDownloadDir();
        if (dir) setDownloadPath(dir);
    }

    const saveSettings = () => {
        SetProxy(proxy);
        SetNamespace(namespace);
        SetDownloadPath(downloadPath);
        setStatus("设置已保存");
        refreshVersion();
    };

    const switchTab = (tab: string) => {
        if (!isDownloading) setActiveTab(tab);
    };

    return (
        <div id="App">
            <aside className="sidebar">
                <div className="brand">
                    <div className="brand-icon"><IconTDL /></div>
                    <span>TDL UI</span>
                </div>
                <nav>
                    <div className={`nav-item ${activeTab === 'download' ? 'active' : ''} ${isDownloading ? 'disabled' : ''}`} onClick={() => switchTab('download')}>
                        <span className="nav-icon"><IconDownload /></span>
                        <span>文件下载</span>
                    </div>
                    <div className={`nav-item ${activeTab === 'upload' ? 'active' : ''} ${isDownloading ? 'disabled' : ''}`} onClick={() => switchTab('upload')}>
                        <span className="nav-icon"><IconUpload /></span>
                        <span>文件上传</span>
                    </div>
                    <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''} ${isDownloading ? 'disabled' : ''}`} onClick={() => switchTab('settings')}>
                        <span className="nav-icon"><IconSettings /></span>
                        <span>设置中心</span>
                    </div>
                </nav>
                <div className="sidebar-footer">
                    <div>Core: {version}</div>
                    <div style={{ marginTop: '4px', opacity: 0.7 }}>{status}</div>
                </div>
            </aside>

            <main className="main-container">
                <div className="page-header">
                    <div className="page-title">
                        {activeTab === 'download' && '文件下载'}
                        {activeTab === 'upload' && '文件上传'}
                        {activeTab === 'settings' && '全局配置'}
                    </div>
                </div>

                <div className="content-scrollable">
                    <div className="card-panel">
                        {activeTab === 'download' && (
                            <>
                                <div className="form-group">
                                    <label>单链接 / 当前任务</label>
                                    <div className="input-row">
                                        <input className="input-main" placeholder="https://t.me/..." value={dlUrl} onChange={e => setDlUrl(e.target.value)} disabled={isDownloading} />
                                        <button className="btn-secondary" onClick={handleBatchImport} disabled={isDownloading}>导入TXT</button>
                                    </div>
                                    {totalTasks > 0 && (
                                        <div className="text-hint">
                                            📊 批量模式: 剩余 {taskQueue.length} / 总计 {totalTasks}
                                        </div>
                                    )}
                                </div>
                                <div className="form-group">
                                    <label>并发线程 ({dlThreads})</label>
                                    <input type="range" min="1" max="64" value={dlThreads} onChange={e => setDlThreads(parseInt(e.target.value))} disabled={isDownloading} />
                                </div>
                                {downloadPath && <div className="text-hint mb-2">下载至: {downloadPath}</div>}
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                                    <button className="btn-secondary" onClick={() => OpenDownloadDir()} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                        <IconFolder /> 打开下载文件夹
                                    </button>
                                    <button
                                        className={`btn-primary ${isDownloading ? 'btn-loading' : ''}`}
                                        onClick={handleDownload}
                                        disabled={!dlUrl || isDownloading}
                                    >
                                        {isDownloading ? '下载中...' : (totalTasks > 0 ? '开始批量下载' : '开始下载')}
                                    </button>
                                </div>
                            </>
                        )}
                        {activeTab === 'upload' && (
                            <>
                                <div className="form-group">
                                    <label>目标对话 / Chat ID</label>
                                    <div style={{ marginBottom: '8px' }}>
                                        <label style={{ display: 'flex', alignItems: 'center', cursor: isDownloading ? 'not-allowed' : 'pointer' }}>
                                            <input
                                                type="checkbox"
                                                checked={upToSaved}
                                                onChange={e => setUpToSaved(e.target.checked)}
                                                disabled={isDownloading}
                                                style={{ marginRight: '8px' }}
                                            />
                                            上传到收藏夹 (Saved Messages)
                                        </label>
                                    </div>
                                    <input
                                        className="input-main"
                                        placeholder="@channel or ID"
                                        value={upChat}
                                        onChange={e => setUpChat(e.target.value)}
                                        disabled={isDownloading || upToSaved}
                                        style={{ opacity: upToSaved ? 0.5 : 1 }}
                                    />
                                </div>
                                <div className="form-group">
                                    <label>文件路径</label>
                                    <div className="input-row">
                                        <input className="input-main" readOnly value={upPath} placeholder="未选择..." disabled={isDownloading} />
                                        <button className="btn-secondary" onClick={pickFile} disabled={isDownloading}>文件</button>
                                        <button className="btn-secondary" onClick={pickFolder} disabled={isDownloading}>目录</button>
                                        <button className="btn-secondary" onClick={pickFolderByFile} disabled={isDownloading} title="进入目录选择任一文件以定位">📂 定位</button>
                                    </div>
                                    <div className="text-hint">注：标准目录选择不显示文件；使用“📂定位”可浏览文件选择目录，需要选中一个文件</div>
                                </div>
                                <div className="form-group">
                                    <label>并发线程 ({upThreads})</label>
                                    <input type="range" min="1" max="64" value={upThreads} onChange={e => setUpThreads(parseInt(e.target.value))} disabled={isDownloading} />
                                </div>
                                <div className="form-group" style={{ display: 'flex', gap: '20px' }}>
                                    <label style={{ display: 'flex', alignItems: 'center', cursor: isDownloading ? 'not-allowed' : 'pointer' }}>
                                        <input type="checkbox" checked={upRemove} onChange={e => setUpRemove(e.target.checked)} disabled={isDownloading} style={{ marginRight: '8px' }} />
                                        删除已上传文件 (Auto-Delete)
                                    </label>
                                    <label style={{ display: 'flex', alignItems: 'center', cursor: isDownloading ? 'not-allowed' : 'pointer' }}>
                                        <input type="checkbox" checked={upAsPhoto} onChange={e => setUpAsPhoto(e.target.checked)} disabled={isDownloading} style={{ marginRight: '8px' }} />
                                        作为照片上传 (As Photo)
                                    </label>
                                </div>
                                <div style={{ textAlign: 'right', marginTop: '10px' }}>
                                    <button
                                        className={`btn-primary ${isDownloading ? 'btn-loading' : ''}`}
                                        onClick={handleUpload}
                                        disabled={!upPath || (!upToSaved && !upChat) || isDownloading}
                                    >
                                        {isDownloading ? '上传中...' : '开始上传'}
                                    </button>
                                </div>
                            </>
                        )}
                        {activeTab === 'settings' && (
                            <>
                                <div className="form-group">
                                    <label>TDL Core Path</label>
                                    <div className="input-row">
                                        <input className="input-main" readOnly value={tdlPath} placeholder="..." />
                                        <button className="btn-secondary" onClick={pickTDLFile}>浏览</button>
                                    </div>
                                </div>
                                <div className="form-group">
                                    <label>Default Download Directory</label>
                                    <div className="input-row">
                                        <input className="input-main" readOnly value={downloadPath} placeholder="默认当前目录" />
                                        <button className="btn-secondary" onClick={pickDownloadDir}>浏览</button>
                                    </div>
                                </div>
                                <div className="form-group">
                                    <label>Proxy Settings</label>
                                    <input className="input-main" placeholder="socks5://127.0.0.1:1080" value={proxy} onChange={e => setProxy(e.target.value)} />
                                </div>
                                <div className="form-group">
                                    <label>Namespace (多账号)</label>
                                    <input className="input-main" placeholder="default" value={namespace} onChange={e => setNamespace(e.target.value)} />
                                </div>
                                <div style={{ textAlign: 'right', marginTop: '20px' }}>
                                    <button className="btn-primary" onClick={saveSettings}>保存配置</button>
                                </div>
                            </>
                        )}
                    </div>

                    {activeTab !== 'settings' && (
                        <div className="card-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '300px', padding: 0, overflow: 'hidden' }}>
                            <div style={{ padding: '16px 24px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, flexShrink: 0 }}>运行日志</div>
                            <div style={{ flex: 1, padding: '16px', background: '#fafafa', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                                <div className="log-box">
                                    {logs.map((log) => (
                                        <div key={log.id} className="log-line">
                                            {log.type !== 'progress' && <span className="log-timestamp">[{new Date().toLocaleTimeString()}]</span>}
                                            {log.text}
                                        </div>
                                    ))}
                                    {logs.length === 0 && <div style={{ color: '#666', textAlign: 'center', marginTop: '40px' }}>暂无日志信息</div>}
                                    <div ref={logEndRef} />
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    )
}

export default App;
