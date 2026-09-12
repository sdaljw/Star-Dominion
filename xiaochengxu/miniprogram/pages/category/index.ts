import { getNativeCategoryById, getNativeToolById, getNativeToolsByCategory, searchNativeTools } from '../../data/toolRegistry';

Page({
  data: {
    category: '',
    title: '工具分类',
    tools: [] as Array<{ id: string; name: string; description: string }>,
    query: '',
    allTools: [] as Array<{ id: string; name: string; description: string; tags: string[] }>,
  },

  onLoad(options: Record<string, string | undefined>) {
    const category = options.category ?? '';
    const categoryInfo = getNativeCategoryById(category);
    const tools = getNativeToolsByCategory(category);
    this.setData({
      category,
      title: categoryInfo?.name ?? '全部工具',
      tools,
      allTools: tools,
    });
  },

  onSearchInput(event: WechatMiniprogram.Input) {
    const query = event.detail.value;
    const allTools = this.data.allTools as Array<{ id: string; name: string; description: string; tags: string[] }>;
    const ids = new Set(searchNativeTools(query).map((tool) => tool.id));
    this.setData({
      query,
      tools: query ? allTools.filter((tool) => ids.has(tool.id)) : allTools,
    });
  },

  openTool(event: WechatMiniprogram.CustomEvent<WechatMiniprogram.IAnyObject>) {
    const id = String(event.detail.id ?? event.currentTarget.dataset.id ?? '');
    const tool = getNativeToolById(id);
    const route = tool?.route ?? '/pages/tool/index';
    wx.navigateTo({ url: `${route}?id=${encodeURIComponent(id)}` });
  },
});
