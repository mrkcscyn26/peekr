/* C1 Interface: JSON client for the C2 API (Section 8.8). Same-origin relative paths only (FR-23).
   Every failure becomes an ApiError with the 8.8 error code; a dropped connection uses code "network". */

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request(method, path, body) {
  const opts = { method, cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    throw new ApiError('network', "Peekr's local server is not responding. Is run.bat still open?", 0);
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    const e = data && data.error;
    throw new ApiError(e ? e.code : 'internal', e ? e.message : `Unexpected HTTP ${res.status}.`, res.status);
  }
  return data;
}

export const get = path => request('GET', path);
export const post = (path, body = {}) => request('POST', path, body);
export const del = path => request('DELETE', path);
