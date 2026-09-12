import { getNativeToolById, NATIVE_CATEGORIES, NATIVE_TOOLS, searchNativeTools } from '../../data/toolRegistry';

Page({
  data: {
    query: '',
    categories: NATIVE_CATEGORIES.slice(0, 8).map((category) => ({
      ...category,
      count: NATIVE_TOOLS.filter((tool) => tool.category === category.id && tool.status === 'ready').length,
    })),
    featuredTools: NATIVE_TOOLS.slice(0, 4),
    searchResults: [] as typeof NATIVE_TOOLS,
  },

  onSearchInput(event: WechatMiniprogram.Input) {
    const query = event.detail.value;
    this.setData({ query, searchResults: searchNativeTools(query) });
  },

  openCategory(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const category = String(event.currentTarget.dataset.category ?? '');
    wx.navigateTo({ url: `/pages/category/index?category=${encodeURIComponent(category)}` });
  },

  openTool(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const id = String(event.detail.id ?? event.currentTarget.dataset.id ?? '');
    const tool = getNativeToolById(id);
    const route = tool?.route ?? '/pages/tool/index';
    wx.navigateTo({ url: `${route}?id=${encodeURIComponent(id)}` });
  },

  onShareAppMessage() {
    return {
      title: '逐梦工具箱｜常用在线工具',
      path: '/pages/home/index',
    };
  },
});
