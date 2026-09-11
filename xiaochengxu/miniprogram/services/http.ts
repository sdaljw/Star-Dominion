export const API_BASE_URL = 'https://zhumenggy.top';

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

export interface RequestJsonOptions {
  method?: HttpMethod;
  data?: WechatMiniprogram.IAnyObject | string | ArrayBuffer;
  header?: Record<string, string>;
}

export function buildApiUrl(path: string): string {
  if (!path || /^https?:\/\//i.test(path) || path.includes('localhost') || path.includes('127.0.0.1')) {
    throw new Error('仅允许使用线上 HTTPS 接口');
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  if (normalizedPath.includes(':80') || normalizedPath.includes(':8000') || normalizedPath.includes(':8012')) {
    throw new Error('仅允许使用线上 HTTPS 接口');
  }

  return `${API_BASE_URL}${normalizedPath}`;
}

export function requestJson<T>(path: string, options: RequestJsonOptions = {}): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    wx.request({
      url: buildApiUrl(path),
      method: options.method ?? 'GET',
      data: options.data,
      header: {
        'content-type': 'application/json',
        ...(options.header ?? {}),
      },
      timeout: 15000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data as T);
          return;
        }
        reject(new Error(`服务请求失败（${response.statusCode}）`));
      },
      fail(error) {
        reject(new Error(error.errMsg || '网络请求失败，请稍后重试'));
      },
    });
  });
}
