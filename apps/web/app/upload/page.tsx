'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getTranslations, type Locale } from '../../lib/i18n';

const defaultLocale: Locale = 'en';

type UploadStatus = 'idle' | 'uploading' | 'queued' | 'error';

type UploadResult = {
  project_id: string;
  job_id: string;
};

export default function UploadPage() {
  const [locale, setLocale] = useState<Locale>(defaultLocale);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const content = getTranslations(locale);

  useEffect(() => {
    const savedLocale = window.localStorage.getItem('vectoryai-locale');
    if (savedLocale === 'en' || savedLocale === 'hu') setLocale(savedLocale);
  }, []);

  function handleLocaleChange(nextLocale: Locale) {
    setLocale(nextLocale);
    window.localStorage.setItem('vectoryai-locale', nextLocale);
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setUploadStatus('idle');
    setUploadResult(null);
    setUploadProgress(0);
  }

  function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) return;

    const formData = new FormData();
    const isPdf = selectedFile.name.toLowerCase().endsWith('.pdf');
    formData.append('file', selectedFile);
    formData.append('page_number', String(isPdf ? Math.max(pageNumber - 1, 0) : 0));

    const request = new XMLHttpRequest();
    request.open('POST', `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/projects/upload`);
    request.upload.addEventListener('progress', (progressEvent) => {
      if (progressEvent.lengthComputable) setUploadProgress(Math.round((progressEvent.loaded / progressEvent.total) * 100));
    });
    request.addEventListener('load', () => {
      if (request.status >= 200 && request.status < 300) {
        setUploadResult(JSON.parse(request.responseText) as UploadResult);
        setUploadStatus('queued');
        setUploadProgress(100);
      } else {
        setUploadStatus('error');
      }
    });
    request.addEventListener('error', () => setUploadStatus('error'));
    setUploadProgress(0);
    setUploadStatus('uploading');
    request.send(formData);
  }

  return (
    <main className="upload-page">
      <nav className="nav shell-width" aria-label={content.navigation.main}>
        <Link className="brand" href="/"><span className="brand-mark">V</span> VectoryAI</Link>
        <div className="nav-links">
          <Link className="back-link" href="/">&#8592; {content.upload.back}</Link>
          <label className="language-picker">
            <span className="sr-only">{content.language.label}</span>
            <select value={locale} onChange={(event) => handleLocaleChange(event.target.value as Locale)} aria-label={content.language.label}>
              <option value="en">EN</option>
              <option value="hu">HU</option>
            </select>
          </label>
        </div>
      </nav>

      <section className="upload-shell shell-width">
        <div className="upload-intro">
          <p className="eyebrow"><span className="eyebrow-dot" /> {content.upload.label}</p>
          <h1>{content.upload.titleBefore}<br /><em>{content.upload.titleEmphasis}</em></h1>
          <p className="lede">{content.upload.description}</p>
        </div>
        <form className="upload-card" onSubmit={handleUpload}>
          <label className="file-picker">
            <span>{selectedFile?.name ?? content.upload.noFile}</span>
            <span className="file-picker-action">{content.upload.chooseFile}</span>
            <input type="file" accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff" onChange={handleFileChange} />
          </label>
          <div className="upload-options">
            <label htmlFor="page-number">{content.upload.page}</label>
            <input id="page-number" type="number" min="1" value={pageNumber} onChange={(event) => setPageNumber(Number(event.target.value) || 1)} disabled={!selectedFile?.name.toLowerCase().endsWith('.pdf')} />
            <span>{content.upload.pageHint}</span>
          </div>
          <p className="upload-hint">{content.upload.acceptedFormats}</p>
          <button className="button button-light upload-submit" type="submit" disabled={!selectedFile || uploadStatus === 'uploading'}>
            {uploadStatus === 'uploading' ? `${content.upload.uploading} ${uploadProgress}%` : content.upload.submit} <span aria-hidden="true">&#8599;</span>
          </button>
          {uploadStatus === 'uploading' && <progress className="upload-progress" max="100" value={uploadProgress} />}
          {uploadStatus === 'queued' && uploadResult && <p className="upload-success">{content.upload.queued}: {content.upload.job} {uploadResult.job_id}<br /><Link className="upload-next-link" href={`/georef?project=${uploadResult.project_id}`}>{content.upload.openGeoref} &#8599;</Link></p>}
          {uploadStatus === 'error' && <p className="upload-error">{content.upload.error} {content.upload.apiUnavailable}</p>}
        </form>
      </section>
    </main>
  );
}
