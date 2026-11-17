self.onmessage = async (event: MessageEvent<{blob: Blob}>) => {
  try {
    const bytes = await new Response(event.data.blob.stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
    self.postMessage({bytes}, {transfer: [bytes]});
  } catch(error) {
    self.postMessage({error: error instanceof Error ? error.message : '三维场景解压失败'});
  }
};
