  /* ---------- colour ---------- */
  function segColour(a, kind) { return css(SERIES[S.mode === 'phase' ? a.ph : S.mode === 'model' ? a.model : kind]); }

