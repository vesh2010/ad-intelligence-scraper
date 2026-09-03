from __future__ import annotations

import pytest
from playwright.async_api import async_playwright

from app.runtime_ads import RUNTIME_ADS_SCRIPT


@pytest.mark.asyncio
async def test_runtime_script_extracts_gpt_and_prebid_objects() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content('<html><body><div id="gpt-slot-1"></div></body></html>')
        await page.evaluate(
            """() => {
                const makeSize = (w, h) => ({ getWidth: () => w, getHeight: () => h });
                const slot = {
                    getSlotElementId: () => 'gpt-slot-1',
                    getAdUnitPath: () => '/1234/news',
                    getSizes: () => [makeSize(300, 250)],
                    getConfig: () => ({ targeting: { pos: ['top'] } }),
                    getTargetingKeys: () => ['pos'],
                    getTargeting: () => ['top'],
                    getResponseInformation: () => ({
                        advertiserId: '42', campaignId: '77', creativeId: '99', creativeTemplateId: '55', lineItemId: '111'
                    })
                };
                const pubads = {
                    getSlots: () => [slot],
                    getTargetingKeys: () => ['site'],
                    getTargeting: () => ['profit']
                };
                window.googletag = { apiReady: true, pubads: () => pubads };
                const bid = {
                    bidder: 'rubicon',
                    adId: 'bid-1',
                    adUnitCode: 'gpt-slot-1',
                    creativeId: 'cr-1',
                    width: 300,
                    height: 250,
                    size: '300x250',
                    cpm: 4.25,
                    currency: 'USD',
                    netRevenue: true,
                    requestTimestamp: 100,
                    responseTimestamp: 171,
                    timeToRespond: 71,
                    mediaType: 'banner',
                    dealId: 'deal-1',
                    status: 'rendered',
                    ttl: 300,
                    adserverTargeting: { hb_bidder: 'rubicon', hb_adid: 'bid-1', hb_pb: '4.25', hb_size: '300x250', hb_format: 'banner' },
                    meta: {
                        advertiserDomains: ['example.com'],
                        advertiserId: 'adv-1',
                        advertiserName: 'Example Advertiser',
                        brandName: 'Example',
                        networkName: 'Example SSP',
                        demandSource: 'prebid'
                    }
                };
                window.pbjs = {
                    adUnits: [{ code: 'gpt-slot-1', mediaTypes: { banner: { sizes: [[300, 250]] } }, bids: [{ bidder: 'rubicon', params: { accountId: 'x' } }] }],
                    getAdserverTargeting: () => ({ 'gpt-slot-1': bid.adserverTargeting }),
                    getBidResponses: () => ({ 'gpt-slot-1': { bids: [bid] } }),
                    getAllWinningBids: () => [bid]
                };
            }"""
        )
        result = await page.evaluate(RUNTIME_ADS_SCRIPT)
        await browser.close()

    assert result["gpt"]["detected"] is True
    assert result["gpt"]["slots"][0]["ad_unit_path"] == "/1234/news"
    assert result["gpt"]["slots"][0]["response_information"]["advertiser_id"] == "42"
    assert result["gpt"]["slots"][0]["response_information"]["creative_template_id"] == "55"
    assert result["prebid"]["detected"] is True
    assert result["prebid"]["bids"][0]["bidder"] == "rubicon"
    assert result["prebid"]["bids"][0]["advertiser_name"] == "Example Advertiser"
    assert result["prebid"]["bids"][0]["adserver_targeting"]["hb_pb"] == "4.25"
    assert result["prebid"]["adserver_targeting"]["gpt-slot-1"]["hb_bidder"] == "rubicon"
    assert result["prebid"]["bids"][0]["rendered"] is True
