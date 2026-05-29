/**
 * Scope classification override component.
 * Requirements: 14.5
 */

import { useState } from 'react';
import {
  Box, Button, FormControl, InputLabel, MenuItem,
  Select, TextField, Typography, Alert, CircularProgress,
} from '@mui/material';
import { emissionsService } from '../services/emissionsService';
import type { EmissionRecord } from '../types';

interface Props {
  record: EmissionRecord;
  onUpdated: (updated: EmissionRecord) => void;
}

export default function ScopeOverride({ record, onUpdated }: Props) {
  const [scope, setScope] = useState<number>(record.scope ?? 1);
  const [justification, setJustification] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async () => {
    if (!justification.trim()) {
      setError('Justification is required for scope override.');
      return;
    }
    setLoading(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await emissionsService.overrideScope(record.id, {
        scope,
        scope_category: scope === 3 ? 6 : null,
        justification,
      });
      onUpdated(updated);
      setSuccess(true);
      setJustification('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Override failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>Override Scope Classification</Typography>
      <Box display="flex" gap={2} alignItems="flex-start" flexWrap="wrap">
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Scope</InputLabel>
          <Select value={scope} label="Scope" onChange={(e) => setScope(Number(e.target.value))}>
            <MenuItem value={1}>Scope 1</MenuItem>
            <MenuItem value={2}>Scope 2</MenuItem>
            <MenuItem value={3}>Scope 3</MenuItem>
          </Select>
        </FormControl>
        <TextField
          size="small"
          label="Justification (required)"
          value={justification}
          onChange={(e) => setJustification(e.target.value)}
          sx={{ flexGrow: 1, minWidth: 200 }}
          required
        />
        <Button
          variant="contained"
          size="small"
          onClick={handleSubmit}
          disabled={loading || !justification.trim()}
          startIcon={loading ? <CircularProgress size={14} /> : undefined}
        >
          Override
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mt: 1 }}>Scope overridden successfully.</Alert>}
    </Box>
  );
}
