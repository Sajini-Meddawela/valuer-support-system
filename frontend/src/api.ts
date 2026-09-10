let token = '';
export const setToken = (value: string) => { token = value; };
export async function api(path: string, method = 'GET', body?: unknown): Promise<any> {
  const form = body instanceof FormData;
  const res = await fetch('/api' + path, {
    method, headers: {...(token ? {Authorization: `Bearer ${token}`} : {}), ...(!form && body !== undefined ? {'Content-Type': 'application/json'} : {})},
    body: body === undefined ? undefined : form ? body : JSON.stringify(body)
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({detail: 'Request failed.'}));
    const detail = data.detail;
    const message = Array.isArray(detail) ? detail.map(x => `${x.loc?.slice(1).join('.')}: ${x.msg}`).join('\n')
      : typeof detail === 'object' ? [detail.message, ...(detail.issues || [])].join('\n') : detail;
    throw new Error(message || 'Request failed.');
  }
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : res.blob();
}
export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
