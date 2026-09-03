import { useQuery } from '@tanstack/react-query';
import { getComplaint } from '../api/complaints';

// Analysis runs asynchronously, so poll until it lands, then stop.
export function useComplaint(id) {
  return useQuery({
    queryKey: ['complaint', id],
    queryFn: () => getComplaint(id),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const s = query.state.data?.analysis_status;
      return s === 'completed' || s === 'failed' ? false : 2000;
    },
  });
}
