import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  // 60 s hard timeout — ensures the UI always exits loading state even when
  // the backend or watsonx.ai stalls. The insights route can take up to ~45 s
  // (LLM batch + mission summary); 60 s gives comfortable headroom.
  timeout: 60_000,
});

export default client;
