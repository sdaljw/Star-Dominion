Component({
  properties: {
    tool: {
      type: Object,
      value: {},
    },
  },

  methods: {
    onTap() {
      const tool = this.data.tool as { id?: string };
      this.triggerEvent('tap', { id: tool.id ?? '' });
    },
  },
});
