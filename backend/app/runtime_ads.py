from __future__ import annotations

from typing import Any

from playwright.async_api import Page


RUNTIME_ADS_SCRIPT = r'''
() => {
  const safe = (fn, fallback = null) => {
    try { return fn(); } catch (_) { return fallback; }
  };
  const arr = (value) => Array.isArray(value) ? value : [];
  const out = {
    gpt: { detected: false, api_ready: false, slots: [], service_targeting: {} },
    prebid: { detected: false, ad_units: [], bids: [], winners: [] }
  };

  const gt = window.googletag;
  if (gt) {
    out.gpt.detected = true;
    out.gpt.api_ready = Boolean(gt.apiReady);
    const pubads = safe(() => gt.pubads(), null);
    const slots = safe(() => pubads ? pubads.getSlots() : [], []);
    out.gpt.service_targeting = safe(() => {
      const keys = arr(pubads.getTargetingKeys());
      return Object.fromEntries(keys.map(k => [k, arr(pubads.getTargeting(k))]));
    }, {});
    out.gpt.slots = slots.map(slot => ({
      element_id: safe(() => slot.getSlotElementId()),
      ad_unit_path: safe(() => slot.getAdUnitPath()),
      sizes: safe(() => arr(slot.getSizes()).map(s => ({
        width: s.getWidth(),
        height: s.getHeight()
      })), []),
      targeting: safe(() => {
        const keys = arr(slot.getTargetingKeys());
        return Object.fromEntries(keys.map(k => [k, arr(slot.getTargeting(k))]));
      }, {}),
      response_information: safe(() => {
        const r = slot.getResponseInformation();
        return r ? {
          advertiser_id: r.advertiserId ?? null,
          campaign_id: r.campaignId ?? null,
          creative_id: r.creativeId ?? null,
          line_item_id: r.lineItemId ?? null
        } : null;
      }, null)
    }));
  }

  const pb = window.pbjs;
  if (pb) {
    out.prebid.detected = true;
    out.prebid.ad_units = safe(() => arr(pb.adUnits).map(u => ({
      code: u.code ?? null,
      media_types: u.mediaTypes ?? null,
      bids: arr(u.bids).map(b => ({
        bidder: b.bidder ?? null,
        params: b.params ?? null
      }))
    })), []);

    const responses = safe(() => pb.getBidResponses(), {});
    const winners = safe(() => pb.getAllWinningBids(), []);
    const winnerKeys = new Set(winners.map(b => `${b.adUnitCode ?? ''}|${b.bidder ?? ''}|${b.adId ?? ''}|${b.creativeId ?? ''}`));
    const bids = [];

    Object.entries(responses || {}).forEach(([adunit, response]) => {
      const arrResponse = Array.isArray(response)
        ? response
        : (response && Array.isArray(response.bids) ? response.bids : []);

      arrResponse.forEach(b => {
        const key = `${adunit}|${b.bidder ?? ''}|${b.adId ?? ''}|${b.creativeId ?? ''}`;
        const meta = b.meta ?? {};
        bids.push({
          ad_unit_code: adunit,
          bidder: b.bidder ?? null,
          ad_id: b.adId ?? null,
          creative_id: b.creativeId ?? null,
          width: b.width ?? null,
          height: b.height ?? null,
          size: b.size ?? null,
          cpm: typeof b.cpm === 'number' ? b.cpm : null,
          currency: b.currency ?? null,
          net_revenue: typeof b.netRevenue === 'boolean' ? b.netRevenue : null,
          time_to_respond_ms: typeof b.timeToRespond === 'number' ? b.timeToRespond : null,
          media_type: b.mediaType ?? meta.mediaType ?? null,
          deal_id: b.dealId ?? null,
          status: b.status ?? null,
          ttl_seconds: typeof b.ttl === 'number' ? b.ttl : null,
          advertiser_domains: arr(meta.advertiserDomains),
          advertiser_id: meta.advertiserId ?? null,
          advertiser_name: meta.advertiserName ?? null,
          agency_id: meta.agencyId ?? null,
          agency_name: meta.agencyName ?? null,
          brand_id: meta.brandId ?? null,
          brand_name: meta.brandName ?? null,
          network_id: meta.networkId ?? null,
          network_name: meta.networkName ?? null,
          demand_source: meta.demandSource ?? null,
          rendered: b.status === 'rendered' || winnerKeys.has(key)
        });
      });
    });

    out.prebid.bids = bids;
    out.prebid.winners = arr(winners).map(b => {
      const meta = b.meta ?? {};
      return {
        ad_unit_code: b.adUnitCode ?? null,
        bidder: b.bidder ?? null,
        ad_id: b.adId ?? null,
        creative_id: b.creativeId ?? null,
        width: b.width ?? null,
        height: b.height ?? null,
        size: b.size ?? null,
        cpm: typeof b.cpm === 'number' ? b.cpm : null,
        currency: b.currency ?? null,
        deal_id: b.dealId ?? null,
        advertiser_domains: arr(meta.advertiserDomains),
        advertiser_id: meta.advertiserId ?? null,
        advertiser_name: meta.advertiserName ?? null,
        brand_name: meta.brandName ?? null,
        network_name: meta.networkName ?? null
      };
    });
  }

  return out;
}
'''


async def collect_runtime_ads(page: Page) -> dict[str, Any]:
    """Read publisher ad-stack objects exposed to the page at a point in time."""
    return await page.evaluate(RUNTIME_ADS_SCRIPT)
