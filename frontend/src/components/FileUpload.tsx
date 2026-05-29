/**
 * File upload component for SAP, Utility, and Travel data ingestion.
 * Requirements: 15.1-15.5
 */

import { useState, useRef } from 'react';
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Typography,
  Alert,
  Stack,
  Chip,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { ingestionService } from '../services/ingestionService';
import type { IngestionResult } from '../types';

type SourceType = 'SAP' | 'UTILITY' | 'TRAVEL';

const SOURCE_CONFIG: Record<SourceType, { label: string; accept: string; hint: string }> = {
  SAP: { label: 'SAP Fuel Procurement', accept: '.txt,.tsv', hint: 'Tab-separated .txt file' },
  UTILITY: { label: 'Utility Electricity', accept: '.csv', hint: 'CSV file' },
  TRAVEL: { label: 'Concur Travel (JSON)', accept: '.json', hint: 'Concur Expense v3 JSON' },
};

export default function FileUpload() {
  const [sourceType, setSourceType] = useState<SourceType>('SAP');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;

    setUploading(true);
    setResult(null);
    setError(null);

    try {
      let res: IngestionResult;
      if (sourceType === 'SAP') {
        res = await ingestionService.uploadSAP(file);
      } else if (sourceType === 'UTILITY') {
        res = await ingestionService.uploadUtility(file);
      } else {
        const text = await file.text();
        const payload = JSON.parse(text);
        res = await ingestionService.postTravel(payload);
      }
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const config = SOURCE_CONFIG[sourceType];

  return (
    <Paper sx={{ p: 3, maxWidth: 600 }}>
      <Typography variant="h6" gutterBottom>Upload Data File</Typography>

      <Stack spacing={3}>
        <FormControl fullWidth>
          <InputLabel>Source System</InputLabel>
          <Select
            value={sourceType}
            label="Source System"
            onChange={(e) => {
              setSourceType(e.target.value as SourceType);
              setResult(null);
              setError(null);
              if (fileInputRef.current) fileInputRef.current.value = '';
            }}
          >
            {(Object.keys(SOURCE_CONFIG) as SourceType[]).map((key) => (
              <MenuItem key={key} value={key}>{SOURCE_CONFIG[key].label}</MenuItem>
            ))}
          </Select>
        </FormControl>

        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {config.hint}
          </Typography>
          <input
            ref={fileInputRef}
            type="file"
            accept={config.accept}
            style={{ display: 'block', marginBottom: 8 }}
          />
        </Box>

        <Button
          variant="contained"
          startIcon={<UploadFileIcon />}
          onClick={handleUpload}
          disabled={uploading}
        >
          {uploading ? 'Uploading…' : 'Upload & Ingest'}
        </Button>

        {uploading && <LinearProgress />}

        {error && <Alert severity="error">{error}</Alert>}

        {result && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>Ingestion Summary</Typography>
            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip label={`Parsed: ${result.records_parsed}`} color="default" />
              <Chip label={`Ingested: ${result.records_ingested}`} color="success" />
              <Chip label={`Errors: ${result.records_with_errors}`} color={result.records_with_errors > 0 ? 'error' : 'default'} />
            </Stack>
            {result.errors.length > 0 && (
              <Box mt={2}>
                <Typography variant="body2" color="error" gutterBottom>Errors:</Typography>
                {result.errors.slice(0, 5).map((e, i) => (
                  <Typography key={i} variant="caption" display="block" color="error">
                    {e.row !== null ? `Row ${e.row}: ` : ''}{e.message}
                  </Typography>
                ))}
                {result.errors.length > 5 && (
                  <Typography variant="caption" color="text.secondary">
                    …and {result.errors.length - 5} more errors
                  </Typography>
                )}
              </Box>
            )}
          </Box>
        )}
      </Stack>
    </Paper>
  );
}
