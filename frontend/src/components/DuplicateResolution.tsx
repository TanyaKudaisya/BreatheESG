/**
 * Duplicate detection resolution component.
 * Requirements: 19.5
 */

import { Box, Typography, Alert, Button } from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import type { DataQualityFlag } from '../types';

interface Props {
  flag: DataQualityFlag;
  onConfirm?: () => void;
}

export default function DuplicateResolution({ flag, onConfirm }: Props) {
  return (
    <Alert
      severity="warning"
      icon={<ContentCopyIcon />}
      action={
        onConfirm && (
          <Button color="inherit" size="small" onClick={onConfirm}>
            Confirm Duplicate
          </Button>
        )
      }
    >
      <Box>
        <Typography variant="body2" fontWeight="bold">Potential Duplicate Detected</Typography>
        <Typography variant="body2">{flag.message}</Typography>
      </Box>
    </Alert>
  );
}
