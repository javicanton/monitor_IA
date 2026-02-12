import React from 'react';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';

function ScoreExplanation() {
  return (
    <Paper 
      elevation={0}
      sx={{
        bgcolor: '#f8f9fa',
        borderLeft: '4px solid #007bff',
        p: 2,
        my: 2,
        borderRadius: 1
      }}
    >
      <Typography variant="body2" color="text.secondary">
        La métrica usada denominada "Overperforming Score" se calcula a partir de las vistas medias de cada canal, por lo que proporciona
        un indicador de cuánto mejor se desempeña un mensaje en comparación con el promedio de su canal. 
        Una puntuación de 1.0 significa que el mensaje tiene un rendimiento promedio, mayor de 1, por encima del promedio y, por debajo
        de 1, por debajo del promedio.
      </Typography>
    </Paper>
  );
}

export default ScoreExplanation; 