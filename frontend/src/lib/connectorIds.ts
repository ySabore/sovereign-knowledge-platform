/** Match admin catalog id to `IntegrationConnector.connector_type` (includes legacy seed aliases). */
export function connectorCatalogMatch(catalogId: string, backendConnectorType: string): boolean {
  const a = catalogId.trim();
  const b = backendConnectorType.trim();
  if (a === b) return true;
  if (a === "google-drive" && b === "gdrive") return true;
  if (a === "gdrive" && b === "google-drive") return true;
  return false;
}
