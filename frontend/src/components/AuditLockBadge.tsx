/**
 * Audit lock status badge and lock/unlock button.
 * Requirements: 13.1-13.3
 */

import { useState } from 'react';
import { Box, Chip, Button, CircularProgress, Tooltip } from '@mui/material';
import LockIcon from '@mui/icons-material/Lock';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import { emissionsService } from '../services/emissionsService';
import type { EmissionRecord } from '../types';

interface Props {
  record: EmissionRecord;
  onUpdated: (updated: EmissionRecord) => void;
  canUnlock?: boolean; // auditor role only
}

export default function AuditLockBadge({ record, onUpdated, canUnlock = false }: Props) {
  const [loading, setLoading] = useState(false);

  const handleLock = async () => {
    setLoading(true);
    try {
      const updated = await emissionsService.lock(record.id);
      onUpdated(updated);
    } finally {
      setLoading(false);
    }
  };

  const handleUnlock = async () => {
    setLoading(true);
    try {
      const updated = await emissionsService.unlock(record.id);
      onUpdated(updated);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      {record.is_locked ? (
        <>
          <Chip icon={<LockIcon />} label="Locked for Audit" color="warning" size="small" />
          {canUnlock && (
            <Tooltip title="Unlock (Auditor only)">
              <span>
                <Button
                  size="small"
                  startIcon={loading ? <CircularProgress size={14} /> : <LockOpenIcon />}
                  onClick={handleUnlock}
                  disabled={loading}
                >
                  Unlock
                </Button>
              </span>
            </Tooltip>
          )}
        </>
      ) : (
        <Button
          size="small"
          variant="outlined"
          startIcon={loading ? <CircularProgress size={14} /> : <LockIcon />}
          onClick={handleLock}
          disabled={loading}
        >
          Lock for Audit
        </Button>
      )}
    </Box>
  );
}
