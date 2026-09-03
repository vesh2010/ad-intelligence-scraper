from __future__ import annotations

RUNTIME_ADS_SCRIPT = r'''
() => {
  const safe = (fn, fallback) => { try { return fn(); } catch (_) { return fallback; } };
  const out = { gpt: { detected: false, slots: [] }, prebid: { detected: false, bids: [], winners: [] } };

  const gt = window.googletag;
  if (gt) {
    out.gpt.detected = true;
    const pubads = safe(() => gt.pubads(), null);
    const slots = safe(() => pubads ? pubads.getSlots() : [], []);
    out.gpt.slots = slots.map(slot => ({
      element_id: safe(() => slot.getSlotElementId(), null),
      ad_unit_path: safe(() => slot.getAdUnitPath(), null),
      sizes: safe(() => slot.getSizes().map(s => ({ width: s.getWidth(), height: s.getHeight() })), []),
      targeting: safe(() => Object.fromEntries(slot.getTargetingKeys().map(k => [k, slot.getTargeting(k)])), {}),
      response_information: safe(() => {
        const r = slot.getResponseInformation();
        return r ? { advertiser_id: r.advertiserId ?? null, campaign_id: r.campaignId ?? null, creative_id: r.creativeId ?? null, line_item_id: r.lineItemId ?? null } : null;
      }, null)
    }));
  }

  const pb = window.pbjs;
  if (pb) {
    out.prebid.detected = true;
    const responses = safe(() => pb.getBidResponses(), {});
    const winners = safe(() => pb.getAllWinningBids(), []);
    const winnerIds = new Set(winners.map(b => b.adId).filter(Boolean));
    const bids = [];
    Object.entries(responses || {}).forEach(([adunit, response]) => {
      const arr = Array.isArray(response) ? response : (response && Array.isArray(response.bids) ? response.bids : []);
      arr.forEach(b => bids.push({
        ad_unit_code: adunit,
        bidder: b.bidder ?? null,
        ad_id: b.adId ?? null,
        creative_id: b.creativeId ?? null,
        width: b.width ?? null,
        height: b.height ?? null,
        size: b.size ?? null,
        cpm: typeof b.cpm === 'number' ? b.cpm : null,
        currency: b.currency ?? null,
        time_to_respond_ms: b.timeToRespond ?? null,
        media_type: b.mediaType ?? null,
        deal_id: b.dealId ?? null,
        rendered: Boolean(b.adId && winnerIds.has(b.adId))
      }));
    });
    out.prebid.bids = bids;
    out.prebid.winners = winners.map(b => ({
      ad_unit_code: b.adUnitCode ?? null,
      bidder: b.bidder ?? null,
      ad_id: b.adId ?? null,
      creative_id: b.creativeId ?? null,
      width: b.width ?? null,
      height: b.height ?? null,
      cpm: typeof b.cpm === 'number' ? b.cpm : null,
      currency: b.currency ?? null,
      deal_id: b.dealId ?? null
    }));
  }
  return out;
}
'''
