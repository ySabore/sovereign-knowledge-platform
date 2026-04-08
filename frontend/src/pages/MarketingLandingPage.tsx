import landingHtml from "../../../docs/sources/RefinedDocuments/landing-page.html?raw";

const wiredLandingHtml = landingHtml
  .replace(
    "<head>",
    `<head>
<base target="_top">`,
  )
  .replace("AI Knowledge Assistant — Enterprise AI Platform", "Sovereign Knowledge Platform — Enterprise AI Platform")
  .replaceAll("AI Knowledge Assistant", "Sovereign Knowledge Platform")
  .replace(
    "</body>",
    `<script>
function wireButton(selector, href) {
  var nodes = document.querySelectorAll(selector);
  nodes.forEach(function (el) {
    el.addEventListener("click", function () {
      if (window.top) {
        window.top.location.href = href;
        return;
      }
      window.location.href = href;
    });
  });
}

wireButton(".nav-ctas .btn-ghost", "/login");
wireButton(".nav-ctas .btn-primary", "/login");
wireButton(".hero-ctas .btn-hero", "/login");
wireButton(".pricing-card .btn-ghost", "/login");
wireButton(".pricing-card.featured .btn-hero", "/login");
wireButton(".final-cta-btns .btn-hero", "/login");

var watchOverview = document.querySelector(".hero-ctas .btn-hero-ghost");
if (watchOverview) {
  watchOverview.addEventListener("click", function () {
    var features = document.getElementById("features");
    if (features) features.scrollIntoView({ behavior: "smooth" });
  });
}

var talkToSalesButtons = document.querySelectorAll(".final-cta-btns .btn-hero-ghost");
talkToSalesButtons.forEach(function (el) {
  el.addEventListener("click", function () {
    if (window.top) {
      window.top.location.href = "mailto:sales@sovereignknowledge.ai";
      return;
    }
    window.location.href = "mailto:sales@sovereignknowledge.ai";
  });
});
</script>
</body>`,
  );

export function MarketingLandingPage() {
  return (
    <iframe
      title="SKP Landing Page"
      srcDoc={wiredLandingHtml}
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        minHeight: "100vh",
        border: "none",
        background: "#080c14",
      }}
    />
  );
}
