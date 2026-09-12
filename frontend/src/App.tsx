import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { SolarSavingsChart, SurveyDatePicker, TariffCard } from "./components/SolusWidgets";

export default function App() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="solus">
      <main>
        <h1>Solus — Philippine Solar Concierge</h1>
        <p>Meralco · VECO · Davao Light — ERC net-metering, 4.5 PSH sizing, typhoon-ready mounting.</p>
        <CopilotSidebar
          defaultOpen
          labels={{
            title: "Solus Concierge",
            initial: "Kumusta! Tell me your DU, monthly bill, roof type, and backup needs.",
          }}
        />
        <section aria-label="Solus live widgets">
          <SolarSavingsChart requiredKwp={3.3} annualSavingsPhp={52000} paybackYears={5.1} />
          <SurveyDatePicker onConfirm={() => {}} />
          <TariffCard utility="Meralco" ratePhp={12.0} />
        </section>
      </main>
    </CopilotKit>
  );
}
