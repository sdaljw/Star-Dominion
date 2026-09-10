import { buildRetryUrl, WEB_ENTRY_URL } from '../../config';

type WebViewStatus = 'loading' | 'ready' | 'error';

Page({
  data: {
    src: WEB_ENTRY_URL,
    status: 'loading' as WebViewStatus,
  },

  onWebViewLoad() {
    this.setData({ status: 'ready' as WebViewStatus });
  },

  onWebViewError() {
    this.setData({ status: 'error' as WebViewStatus });
  },

  retry() {
    this.setData({
      src: buildRetryUrl(Date.now()),
      status: 'loading' as WebViewStatus,
    });
  },

  onShareAppMessage() {
    return {
      title: '逐梦工具箱｜常用在线工具',
      path: '/pages/index/index',
    };
  },
});
