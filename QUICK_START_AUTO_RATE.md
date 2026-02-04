# 🚀 Quick Start Guide - Auto-Rate All Feature

## What Is It?
One-click AI analysis that rates all your uploaded profile test images at once, generating a complete profile analysis like your Custom GPT.

## How To Use

### Step 1: Upload Images
1. Go to **🖼️ Images** tab
2. Upload all test images for your profile
3. Images save to `profile_results/{profile_id}/`

### Step 2: Run AI Analysis
1. Go to **⭐ Rate** tab
2. Scroll to top, click **🤖 Auto-Rate All** button
3. (Optional) Enter a profile label suggestion
4. Click **🚀 Start AI Analysis**
5. Wait 30-60 seconds

### Step 3: Review Results
- Profile Label generated
- Profile DNA traits (5-10 items)
- All tests rated with:
  - Affinity (native_fit/workable/resistant)
  - Score (1-10)
  - Confidence level
  - Detailed commentary

### Step 4: Use Results
- Go to **🎯 Recommend** tab
- Enter new prompts
- System recommends best profiles based on AI analysis

## What The AI Analyzes

### Profile Label (2-4 words)
Examples:
- "Moody Urban Explorer"
- "Vibrant Nature Maximalist"
- "Minimalist Architectural"
- "Dramatic Chiaroscuro"

### Profile DNA (5-10 traits)
Examples:
- "Prefers dramatic lighting contrasts"
- "Gravitates toward cool color palettes"
- "Excels at atmospheric depth"
- "Struggles with busy compositions"
- "Natural talent for moody, cinematic scenes"

### Per-Test Ratings

**Affinity Levels:**
- **native_fit**: Profile naturally excels (this is what it's made for)
- **workable**: Profile can adapt but has limitations
- **resistant**: Profile struggles significantly

**Score**: 1-10 quality rating

**Confidence**: 0.0-1.0 how sure the AI is

**Commentary**: 2-3 sentences explaining:
- What works well
- What doesn't work
- Why the profile succeeds/struggles

## Tips

### Get Best Results
- Upload ALL test images before running
- Use high-quality 16:9 images
- Provide profile label hint if you know the vibe
- Review AI ratings - adjust if needed

### When To Use Auto-Rate vs Manual
- **Auto-Rate**: First pass, 5+ profiles, time-limited
- **Manual**: Deep analysis, 1-2 profiles, learning patterns

### Cost
- ~$0.10-0.30 per batch (20 images)
- Uses GPT-4o-mini (cost-effective with vision)
- Cheaper than manual time investment

## Comparison

### Before (Manual)
1. Upload image
2. Read prompt
3. Look at image
4. Choose affinity
5. Rate 1-10
6. Write commentary
7. Repeat 20 times
8. Think of DNA traits
9. Create profile label

**Time**: 30-45 minutes per profile

### After (Auto-Rate All)
1. Upload all images
2. Click button
3. Wait 1 minute
4. Review results

**Time**: 5 minutes per profile

## Example Output

```json
{
  "profile_label": "Moody Cinematic Realist",
  "profile_dna": [
    "Excels at low-light urban environments",
    "Natural talent for atmospheric depth",
    "Prefers muted, desaturated color palettes",
    "Strong with architectural subjects",
    "Struggles with bright, vibrant scenes"
  ],
  "ratings": {
    "Night Urban Traffic": {
      "affinity": "native_fit",
      "score": 9,
      "confidence": 0.95,
      "commentary": "This profile absolutely nails the moody urban night scene with perfect lighting balance and atmospheric depth. The color palette is naturally aligned with the profile's strengths. Only minor critique is slightly soft detail in highlights."
    },
    "Tropical Beach Sunset": {
      "affinity": "resistant",
      "score": 4,
      "confidence": 0.85,
      "commentary": "Profile struggles with bright, warm scenes. The vibrant colors feel forced and unnatural. The composition is decent but lacks the profile's usual atmospheric sophistication. This is outside the profile's comfort zone."
    }
  }
}
```

## Troubleshooting

**Button doesn't appear**
- Make sure you're in Rate tab
- Scroll to top where metrics are shown

**"No images uploaded" warning**
- Upload images in Images tab first
- Check `profile_results/{profile_id}/` folder exists

**API error**
- Check `OPENAI_API_KEY` environment variable is set
- Verify OpenAI account has credits
- Check internet connection

**Results look wrong**
- AI makes mistakes - review and adjust
- Try running again with profile label hint
- Manual rate any outliers

**Takes too long**
- Normal: 30-60 seconds for 20 images
- Over 2 minutes: Check internet connection
- Try fewer images (test with 5-10 first)

## Next Steps

After auto-rating:
1. Review Profile DNA - edit if needed
2. Adjust any outlier ratings manually
3. Use Recommend tab for new prompts
4. Compare multiple profiles
5. Archive v1 tests, build v3 suite

---

**That's it!** You can now analyze profiles 10x faster with AI. 🎉
