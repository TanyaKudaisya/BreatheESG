/**
 * Emissions page — data grid with record detail modal.
 */

import { useState } from 'react';
import EmissionsGrid from '../components/EmissionsGrid';
import RecordDetailModal from '../components/RecordDetailModal';
import type { EmissionRecord } from '../types';

export default function EmissionsPage() {
  const [selectedRecord, setSelectedRecord] = useState<EmissionRecord | null>(null);

  return (
    <>
      <EmissionsGrid onRowClick={setSelectedRecord} />
      <RecordDetailModal
        record={selectedRecord}
        open={selectedRecord !== null}
        onClose={() => setSelectedRecord(null)}
      />
    </>
  );
}
