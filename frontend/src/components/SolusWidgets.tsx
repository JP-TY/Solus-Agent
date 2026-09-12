export function SolarSavingsChart({ requiredKwp, annualSavingsPhp, paybackYears }: {
  requiredKwp: number; annualSavingsPhp: number; paybackYears: number;
}) {
  return (
    <div data-testid="solar-savings-chart">
      <h3>Solus Sizing Result</h3>
      <p>Array: {requiredKwp} kWp</p>
      <p>Annual blended savings: PHP {annualSavingsPhp.toLocaleString()}</p>
      <p>Simple payback: {paybackYears} years</p>
    </div>
  );
}

export function SurveyDatePicker({ onConfirm }: { onConfirm: (date: string) => void }) {
  return (
    <div data-testid="survey-date-picker">
      <h3>Confirm ocular survey date</h3>
      <input type="date" aria-label="Survey date" id="solus-survey-date" />
      <button onClick={() => {
        const el = document.getElementById("solus-survey-date") as HTMLInputElement;
        onConfirm(el?.value ?? "");
      }}>Confirm survey</button>
    </div>
  );
}

export function TariffCard({ utility, ratePhp }: { utility: string; ratePhp: number }) {
  return (
    <div data-testid="tariff-card">
      <h3>{utility} live tariff</h3>
      <p>Generation charge: PHP {ratePhp}/kWh (via Solus browser tool)</p>
    </div>
  );
}
