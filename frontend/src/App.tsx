import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { SolarSavingsChart, SurveyDatePicker, TariffCard } from "./components/SolusWidgets";

export default function App() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="solus">
      <div className="solus-page">
        <header className="solus-hero">
          <div className="solus-eyebrow">Bedrock AgentCore · Strands · Nova 2 Lite</div>
          <h1>Solus <span className="sun">☀</span> Philippine Solar Concierge</h1>
          <p className="solus-sub">
            Meralco · VECO · Davao Light — ERC net-metering guidance, 4.5 PSH
            system sizing, and typhoon-ready mounting advice, with a concierge
            that remembers you.
          </p>
          <span className="solus-status"><span className="dot" />Runtime live · 6/6 tools green</span>
        </header>
        <section className="solus-grid" aria-label="Solus live widgets">
          <SolarSavingsChart requiredKwp={3.3} annualSavingsPhp={52000} paybackYears={5.1} />
          <SurveyDatePicker onConfirm={() => {}} />
          <TariffCard utility="Meralco" ratePhp={12.0} />
        </section>
        <footer className="solus-foot">
          github.com/JP-TY/Solus-Agent · chat in the sidebar — tell Solus your DU, bill, roof and backup needs
        </footer>
        <CopilotSidebar
          defaultOpen
          labels={{
            title: "Solus Concierge",
            initial: "Kumusta! Tell me your DU, monthly bill, roof type, and backup needs.",
          }}
        />
      </div>
    </CopilotKit>
  );
}
