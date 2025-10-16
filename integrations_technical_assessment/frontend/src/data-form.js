import { useState } from 'react';
import { Box, Button, Table, TableHead, TableRow, TableCell, TableBody, Paper } from '@mui/material';

import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'Hubspot': 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState([]);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            const base = process.env.REACT_APP_API_BASE || 'http://localhost:8000';
            const response = await axios.post(`${base}/integrations/${endpoint}/load`, formData);
            const data = Array.isArray(response.data) ? response.data : [];
            setLoadedData(data);
        } catch (e) {
            alert(e?.response?.data?.detail);
        }
    }

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='column' width='100%'>
            {loadedData.length > 0 && (
                    <Paper sx={{ mt: 2, p: 1, overflowX: 'auto' }}>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>ID</TableCell>
                                    <TableCell>Name</TableCell>
                                    <TableCell>Type</TableCell>
                                    <TableCell>Created</TableCell>
                                    <TableCell>Updated</TableCell>
                                    <TableCell>URL</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {loadedData.map((item, idx) => (
                                    <TableRow key={item?.id || idx}>
                                        <TableCell>{item?.id}</TableCell>
                                        <TableCell>{item?.name}</TableCell>
                                        <TableCell>{item?.type}</TableCell>
                                        <TableCell>{item?.creation_time || ''}</TableCell>
                                        <TableCell>{item?.last_modified_time || ''}</TableCell>
                                        <TableCell>
                                            {item?.url ? <a href={item.url} target="_blank" rel="noreferrer">Open</a> : ''}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </Paper>
                )}

                <Button
                    onClick={handleLoad}
                    sx={{mt: 2}}
                    variant='contained'
                >
                    Load Data
                </Button>
                <Button
                    onClick={() => setLoadedData([])}
                    sx={{mt: 1}}
                    variant='contained'
                >
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
}
